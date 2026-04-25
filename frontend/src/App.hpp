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
    void handleInput(const LayoutRects& layout);
    void processBackendEvents();
    void draw(const LayoutRects& layout);
    void addConsole(const std::string& level, const std::string& text);
    std::vector<std::string> wrapTextToWidth(const std::string& text, int fontSize, int maxWidth) const;

    BackendProcess backend_;
    WebSocketClient wsClient_;
    std::vector<ChatMessage> chat_;
    std::vector<ConsoleEvent> console_;
    std::vector<std::string> backendLogs_;
    std::string inputBuffer_;
    bool hasStreamingAssistant_ = false;
    int conversationScrollLines_ = 0;
};
