#pragma once

#include <mutex>
#include <string>
#include <vector>

class BackendProcess {
  public:
    ~BackendProcess();

    bool ensureBackendRunning();
    bool waitUntilReady(int timeoutMs);
    std::vector<std::string> pollLogLines();
    void stopIfStarted();

  private:
    bool healthCheck();
    bool launchBackendWithPython(const std::wstring& pythonExePath);
    void appendLogLine(const std::string& line);
    bool startedByFrontend_ = false;
    std::mutex logMutex_;
    std::vector<std::string> pendingLogLines_;

#ifdef _WIN32
    void closeLogPipe();
    void* processHandle_ = nullptr;
    void* logReadPipe_ = nullptr;
    void* logThread_ = nullptr;
#endif
};
