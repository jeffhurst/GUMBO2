#pragma once

#include <string>

class BackendProcess {
  public:
    bool ensureBackendRunning();
    bool waitUntilReady(int timeoutMs);
    void stopIfStarted();

  private:
    bool healthCheck();
    bool startedByFrontend_ = false;

#ifdef _WIN32
    void* processHandle_ = nullptr;
#endif
};
