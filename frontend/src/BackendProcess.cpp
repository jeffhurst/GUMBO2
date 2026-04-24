#include "BackendProcess.hpp"

#include <chrono>
#include <thread>

#ifdef _WIN32
#include <windows.h>
#include <winhttp.h>
#pragma comment(lib, "winhttp.lib")
#endif

bool BackendProcess::ensureBackendRunning() {
    if (healthCheck()) {
        return true;
    }
#ifdef _WIN32
    STARTUPINFOW si{};
    PROCESS_INFORMATION pi{};
    si.cb = sizeof(si);

    std::wstring cmd =
        L".venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000";
    if (CreateProcessW(nullptr, cmd.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW, nullptr,
                       L"..\\backend", &si, &pi)) {
        startedByFrontend_ = true;
        processHandle_ = pi.hProcess;
        CloseHandle(pi.hThread);
        return true;
    }

    std::wstring fallback = L"python -m uvicorn app.main:app --host 127.0.0.1 --port 8000";
    if (CreateProcessW(nullptr, fallback.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW, nullptr,
                       L"..\\backend", &si, &pi)) {
        startedByFrontend_ = true;
        processHandle_ = pi.hProcess;
        CloseHandle(pi.hThread);
        return true;
    }
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

void BackendProcess::stopIfStarted() {
#ifdef _WIN32
    if (startedByFrontend_ && processHandle_ != nullptr) {
        TerminateProcess(static_cast<HANDLE>(processHandle_), 0);
        CloseHandle(static_cast<HANDLE>(processHandle_));
        processHandle_ = nullptr;
    }
#endif
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
