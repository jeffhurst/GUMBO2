#include "BackendProcess.hpp"

#include <chrono>
#include <thread>
#include <utility>

#ifdef _WIN32
#include <windows.h>
#include <winhttp.h>
#pragma comment(lib, "winhttp.lib")
#endif

BackendProcess::~BackendProcess() {
    stopIfStarted();
}

bool BackendProcess::ensureBackendRunning() {
    if (healthCheck()) {
        return true;
    }
#ifdef _WIN32
    if (launchBackendWithPython(L"..\\backend\\.venv\\Scripts\\python.exe")) return true;
    if (launchBackendWithPython(L"python")) return true;
#endif
    return false;
}

bool BackendProcess::waitUntilReady(int timeoutMs) {
    const int stepMs = 250;
    for (int elapsed = 0; elapsed < timeoutMs; elapsed += stepMs) {
        if (healthCheck()) {
            return true;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(stepMs));
    }
    return false;
}

std::vector<std::string> BackendProcess::pollLogLines() {
    std::lock_guard<std::mutex> lock(logMutex_);
    std::vector<std::string> lines = std::move(pendingLogLines_);
    pendingLogLines_.clear();
    return lines;
}

void BackendProcess::stopIfStarted() {
#ifdef _WIN32
    closeLogPipe();
    if (logThread_ != nullptr) {
        WaitForSingleObject(static_cast<HANDLE>(logThread_), 500);
        CloseHandle(static_cast<HANDLE>(logThread_));
        logThread_ = nullptr;
    }
    if (startedByFrontend_ && processHandle_ != nullptr) {
        TerminateProcess(static_cast<HANDLE>(processHandle_), 0);
    }
    if (processHandle_ != nullptr) {
        CloseHandle(static_cast<HANDLE>(processHandle_));
        processHandle_ = nullptr;
    }
    startedByFrontend_ = false;
#endif
}

void BackendProcess::keepBackendRunningOnExit() {
    startedByFrontend_ = false;
}

bool BackendProcess::healthCheck() {
#ifdef _WIN32
    HINTERNET session = WinHttpOpen(L"Gumbo/1.0", WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
                                    WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!session) {
        return false;
    }

    HINTERNET connect = WinHttpConnect(session, L"127.0.0.1", 8000, 0);
    if (!connect) {
        WinHttpCloseHandle(session);
        return false;
    }

    HINTERNET request = WinHttpOpenRequest(connect, L"GET", L"/health", nullptr,
                                           WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, 0);

    bool ok = false;
    if (request && WinHttpSendRequest(request, WINHTTP_NO_ADDITIONAL_HEADERS, 0,
                                      WINHTTP_NO_REQUEST_DATA, 0, 0, 0) &&
        WinHttpReceiveResponse(request, nullptr)) {
        DWORD code = 0;
        DWORD size = sizeof(code);
        if (WinHttpQueryHeaders(request,
                                WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
                                WINHTTP_HEADER_NAME_BY_INDEX, &code, &size,
                                WINHTTP_NO_HEADER_INDEX)) {
            ok = code == 200;
        }
    }

    if (request) WinHttpCloseHandle(request);
    WinHttpCloseHandle(connect);
    WinHttpCloseHandle(session);
    return ok;
#else
    return false;
#endif
}

void BackendProcess::appendLogLine(const std::string& line) {
    std::lock_guard<std::mutex> lock(logMutex_);
    pendingLogLines_.push_back(line);
    if (pendingLogLines_.size() > 200) {
        pendingLogLines_.erase(pendingLogLines_.begin(), pendingLogLines_.begin() + 50);
    }
}

#ifdef _WIN32
void BackendProcess::closeLogPipe() {
    if (logReadPipe_ != nullptr) {
        CloseHandle(static_cast<HANDLE>(logReadPipe_));
        logReadPipe_ = nullptr;
    }
}

bool BackendProcess::launchBackendWithPython(const std::wstring& pythonExePath) {
    SECURITY_ATTRIBUTES sa{};
    sa.nLength = sizeof(sa);
    sa.bInheritHandle = TRUE;

    HANDLE readPipe = nullptr;
    HANDLE writePipe = nullptr;
    if (!CreatePipe(&readPipe, &writePipe, &sa, 0)) {
        return false;
    }
    SetHandleInformation(readPipe, HANDLE_FLAG_INHERIT, 0);

    STARTUPINFOW si{};
    PROCESS_INFORMATION pi{};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdOutput = writePipe;
    si.hStdError = writePipe;

    std::wstring cmd =
        pythonExePath + L" -m uvicorn app.main:app --host 127.0.0.1 --port 8000";
    BOOL started = CreateProcessW(nullptr, cmd.data(), nullptr, nullptr, TRUE, CREATE_NO_WINDOW, nullptr,
                                  L"..\\backend", &si, &pi);
    CloseHandle(writePipe);

    if (!started) {
        CloseHandle(readPipe);
        return false;
    }

    startedByFrontend_ = true;
    processHandle_ = pi.hProcess;
    CloseHandle(pi.hThread);
    logReadPipe_ = readPipe;
    appendLogLine("Backend process launched.");

    HANDLE threadHandle = CreateThread(
        nullptr, 0,
        [](LPVOID param) -> DWORD {
            auto* self = static_cast<BackendProcess*>(param);
            HANDLE pipe = static_cast<HANDLE>(self->logReadPipe_);
            if (!pipe) return 0;

            std::string buffer;
            char chunk[256];
            DWORD bytesRead = 0;
            while (ReadFile(pipe, chunk, sizeof(chunk), &bytesRead, nullptr) && bytesRead > 0) {
                buffer.append(chunk, chunk + bytesRead);
                size_t pos = 0;
                while ((pos = buffer.find('\n')) != std::string::npos) {
                    std::string line = buffer.substr(0, pos);
                    if (!line.empty() && line.back() == '\r') line.pop_back();
                    self->appendLogLine(line);
                    buffer.erase(0, pos + 1);
                }
            }
            if (!buffer.empty()) self->appendLogLine(buffer);
            return 0;
        },
        this, 0, nullptr);

    if (threadHandle != nullptr) {
        logThread_ = threadHandle;
    } else {
        appendLogLine("warning: failed to start backend log capture thread.");
    }

    return true;
}
#endif
