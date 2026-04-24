#pragma once

#include <mutex>
#include <optional>
#include <queue>
#include <string>

#include <ixwebsocket/IXWebSocket.h>

struct IncomingEvent {
    std::string type;
    std::string message;
    std::string text;
    std::string level;
    std::string path;
};

class WebSocketClient {
  public:
    ~WebSocketClient();

    bool connect(const std::string& url);
    void sendUserMessage(const std::string& text);
    std::optional<IncomingEvent> pollEvent();
    void close();

  private:
    ix::WebSocket socket_;
    std::mutex mutex_;
    std::queue<IncomingEvent> events_;
    bool connected_ = false;
};
