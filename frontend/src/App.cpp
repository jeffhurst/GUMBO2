#include "App.hpp"

#include "raylib.h"

#include <algorithm>
#include <sstream>

void App::run() {
    SetConfigFlags(FLAG_WINDOW_RESIZABLE);
    InitWindow(1280, 720, "Gumbo MVP");
    ToggleFullscreen();
    SetTargetFPS(60);

    addConsole("info", "Starting backend...");
    if (!backend_.ensureBackendRunning()) {
        addConsole("error", "Failed to launch backend process.");
    }

    if (backend_.waitUntilReady(10000)) {
        addConsole("info", "Backend is ready.");
    } else {
        addConsole("warning", "Backend health check timed out.");
    }

    wsClient_.connect("ws://127.0.0.1:8000/ws/chat");
    addConsole("info", "WebSocket connect requested.");

    while (!WindowShouldClose()) {
        if (IsKeyPressed(KEY_ESCAPE)) {
            break;
        }

        const auto layout = ComputeLayout(GetScreenWidth(), GetScreenHeight());

        handleInput(layout);
        processBackendEvents();

        BeginDrawing();
        ClearBackground(Color{18, 18, 24, 255});
        draw(layout);
        EndDrawing();
    }

    wsClient_.close();
    backend_.keepBackendRunningOnExit();
    CloseWindow();
}

void App::handleInput(const LayoutRects& layout) {
    const Vector2 mousePos = GetMousePosition();
    const bool mouseInConversation = CheckCollisionPointRec(mousePos, layout.conversation);
    const float wheelDelta = GetMouseWheelMove();
    if (mouseInConversation && wheelDelta != 0.0f) {
        conversationScrollLines_ += (wheelDelta > 0.0f ? 3 : -3);
        conversationScrollLines_ = std::max(0, conversationScrollLines_);
    }

    int key = GetCharPressed();
    while (key > 0) {
        if (key >= 32 && key <= 126) {
            inputBuffer_.push_back(static_cast<char>(key));
        }
        key = GetCharPressed();
    }

    if (IsKeyPressed(KEY_BACKSPACE) && !inputBuffer_.empty()) {
        inputBuffer_.pop_back();
    }

    if (IsKeyPressed(KEY_ENTER)) {
        const auto text = inputBuffer_;
        inputBuffer_.clear();
        if (text.empty()) {
            addConsole("warning", "Empty input ignored.");
            return;
        }

        chat_.push_back({"user", text});
        chat_.push_back({"assistant", ""});
        hasStreamingAssistant_ = true;
        wsClient_.sendUserMessage(text);
        addConsole("info", "Sent user message.");
    }
}

void App::processBackendEvents() {
    auto backendLines = backend_.pollLogLines();
    for (const auto& line : backendLines) {
        backendLogs_.push_back(line);
        if (backendLogs_.size() > 300) {
            backendLogs_.erase(backendLogs_.begin(), backendLogs_.begin() + 80);
        }
    }

    while (true) {
        auto event = wsClient_.pollEvent();
        if (!event.has_value()) {
            break;
        }

        if (event->type == "token") {
            if (hasStreamingAssistant_ && !chat_.empty()) {
                chat_.back().text += event->text;
            }
        } else if (event->type == "final" || event->type == "assistant_message") {
            if (hasStreamingAssistant_ && !chat_.empty()) {
                chat_.back().text = event->text;
            }
            hasStreamingAssistant_ = false;
        } else if (event->type == "status") {
            addConsole("info", event->message);
        } else if (event->type == "alert") {
            addConsole(event->level.empty() ? "error" : event->level, event->message);
        } else if (event->type == "turn_saved") {
            addConsole("info", "Turn saved: " + event->path);
        }
    }
}

void App::draw(const LayoutRects& layout) {
    DrawRectangleRec(layout.conversation, Color{35, 35, 46, 255});
    DrawRectangleRec(layout.input, Color{44, 44, 56, 255});
    DrawRectangleRec(layout.fdg, Color{28, 34, 42, 255});
    DrawRectangleRec(layout.console, Color{22, 22, 28, 255});

    DrawText("Backend Output + Conversation", static_cast<int>(layout.conversation.x) + 12,
             static_cast<int>(layout.conversation.y) + 10, 20, RAYWHITE);
    DrawText("Input", static_cast<int>(layout.input.x) + 12, static_cast<int>(layout.input.y) + 8, 18,
             RAYWHITE);
    DrawText("FDG / Memory", static_cast<int>(layout.fdg.x) + 12, static_cast<int>(layout.fdg.y) + 10, 20,
             RAYWHITE);
    DrawText("Console", static_cast<int>(layout.console.x) + 12, static_cast<int>(layout.console.y) + 10,
             20, RAYWHITE);

    const int padding = 12;
    const int conversationContentX = static_cast<int>(layout.conversation.x) + padding;
    const int conversationContentY = static_cast<int>(layout.conversation.y) + 40;
    const int conversationWidth = static_cast<int>(layout.conversation.width) - (padding * 2);
    const int lineHeight = 22;

    struct RenderLine {
        std::string text;
        Color color;
    };

    std::vector<RenderLine> lines;
    lines.push_back({"Backend:", GOLD});
    for (const auto& backendLine : backendLogs_) {
        for (const auto& wrapped : wrapTextToWidth(backendLine, 16, conversationWidth)) {
            lines.push_back({wrapped, LIGHTGRAY});
        }
    }
    lines.push_back({"", LIGHTGRAY});
    lines.push_back({"Chat:", SKYBLUE});

    for (const auto& msg : chat_) {
        const std::string prefix = msg.role == "user" ? "You: " : "Gumbo: ";
        const Color color = msg.role == "user" ? SKYBLUE : LIGHTGRAY;
        const auto wrappedMessage = wrapTextToWidth(prefix + msg.text, 18, conversationWidth);
        for (const auto& wrappedLine : wrappedMessage) {
            lines.push_back({wrappedLine, color});
        }
    }

    const int availableHeight = static_cast<int>(layout.conversation.height) - 50;
    const int visibleLineCount = std::max(1, availableHeight / lineHeight);
    const int maxScroll = std::max(0, static_cast<int>(lines.size()) - visibleLineCount);
    conversationScrollLines_ = std::min(conversationScrollLines_, maxScroll);

    const int startLine = std::max(0, static_cast<int>(lines.size()) - visibleLineCount - conversationScrollLines_);
    const int endLine = std::min(static_cast<int>(lines.size()), startLine + visibleLineCount);

    BeginScissorMode(static_cast<int>(layout.conversation.x) + 2, static_cast<int>(layout.conversation.y) + 36,
                     static_cast<int>(layout.conversation.width) - 4,
                     static_cast<int>(layout.conversation.height) - 40);
    int y = conversationContentY;
    for (int i = startLine; i < endLine; ++i) {
        DrawText(lines[i].text.c_str(), conversationContentX, y, 18, lines[i].color);
        y += lineHeight;
    }
    EndScissorMode();

    const std::string cursor = ((GetTime() * 2) - static_cast<int>(GetTime() * 2) > 0.5) ? "_" : " ";
    DrawText((inputBuffer_ + cursor).c_str(), static_cast<int>(layout.input.x) + 12,
             static_cast<int>(layout.input.y) + 40, 22, WHITE);

    int cx = static_cast<int>(layout.fdg.x + layout.fdg.width / 2.0f);
    int cy = static_cast<int>(layout.fdg.y + layout.fdg.height / 2.0f);
    DrawCircle(cx, cy, 48.0f, Color{120, 180, 255, 255});

    int consoleY = static_cast<int>(layout.console.y) + 40;
    const int maxConsole = 8;
    int cstart = static_cast<int>(console_.size()) > maxConsole ? static_cast<int>(console_.size()) - maxConsole : 0;
    for (int i = cstart; i < static_cast<int>(console_.size()); ++i) {
        const auto& ev = console_[i];
        Color color = LIGHTGRAY;
        if (ev.level == "error") color = RED;
        if (ev.level == "warning") color = ORANGE;
        if (ev.level == "info") color = GREEN;
        DrawText(ev.text.c_str(), static_cast<int>(layout.console.x) + 12, consoleY, 18, color);
        consoleY += 22;
    }
}

void App::addConsole(const std::string& level, const std::string& text) {
    console_.push_back({level, text});
    if (console_.size() > 100) {
        console_.erase(console_.begin(), console_.begin() + 20);
    }
}

std::vector<std::string> App::wrapTextToWidth(const std::string& text, int fontSize, int maxWidth) const {
    if (text.empty()) {
        return {""};
    }

    std::vector<std::string> lines;
    std::istringstream stream(text);
    std::string word;
    std::string currentLine;

    while (stream >> word) {
        std::string candidate = currentLine.empty() ? word : currentLine + " " + word;
        if (MeasureText(candidate.c_str(), fontSize) <= maxWidth) {
            currentLine = std::move(candidate);
            continue;
        }

        if (!currentLine.empty()) {
            lines.push_back(currentLine);
            currentLine.clear();
        }

        if (MeasureText(word.c_str(), fontSize) <= maxWidth) {
            currentLine = word;
            continue;
        }

        std::string splitChunk;
        for (char ch : word) {
            std::string splitCandidate = splitChunk + ch;
            if (MeasureText(splitCandidate.c_str(), fontSize) > maxWidth && !splitChunk.empty()) {
                lines.push_back(splitChunk);
                splitChunk.clear();
            }
            splitChunk.push_back(ch);
        }
        if (!splitChunk.empty()) {
            currentLine = splitChunk;
        }
    }

    if (!currentLine.empty()) {
        lines.push_back(currentLine);
    }

    if (lines.empty()) {
        lines.push_back("");
    }
    return lines;
}
