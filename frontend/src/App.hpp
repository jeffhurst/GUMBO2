#pragma once

#include <string>
#include <vector>

#include "BackendProcess.hpp"
#include "Layout.hpp"
#include "WebSocketClient.hpp"

struct ChatMessage {
    std::string role;
    std::string text;
};

struct ConsoleEvent {
    std::string level;
    std::string text;
};

class App {
  public:
    void run();

  private:
    void handleInput();
    void processBackendEvents();
    void draw(const LayoutRects& layout);
    void addConsole(const std::string& level, const std::string& text);

    BackendProcess backend_;
    WebSocketClient wsClient_;
    std::vector<ChatMessage> chat_;
    std::vector<ConsoleEvent> console_;
    std::string inputBuffer_;
    bool hasStreamingAssistant_ = false;
};
