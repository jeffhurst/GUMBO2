#include "App.hpp"

#include "raylib.h"

#include <algorithm>

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

        handleInput();
        processBackendEvents();

        const auto layout = ComputeLayout(GetScreenWidth(), GetScreenHeight());

        BeginDrawing();
        ClearBackground(Color{18, 18, 24, 255});
        draw(layout);
        EndDrawing();
    }

    wsClient_.close();
    backend_.stopIfStarted();
    CloseWindow();
}

void App::handleInput() {
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
    while (true) {
        auto event = wsClient_.pollEvent();
        if (!event.has_value()) {
            break;
        }

        if (event->type == "token") {
            if (hasStreamingAssistant_ && !chat_.empty()) {
                chat_.back().text += event->text;
            }
        } else if (event->type == "final") {
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

    DrawText("Conversation", static_cast<int>(layout.conversation.x) + 12,
             static_cast<int>(layout.conversation.y) + 10, 20, RAYWHITE);
    DrawText("Input", static_cast<int>(layout.input.x) + 12, static_cast<int>(layout.input.y) + 8, 18,
             RAYWHITE);
    DrawText("FDG / Memory", static_cast<int>(layout.fdg.x) + 12, static_cast<int>(layout.fdg.y) + 10, 20,
             RAYWHITE);
    DrawText("Console", static_cast<int>(layout.console.x) + 12, static_cast<int>(layout.console.y) + 10,
             20, RAYWHITE);

    int y = static_cast<int>(layout.conversation.y) + 40;
    const int maxMessages = 18;
    int start = static_cast<int>(chat_.size()) > maxMessages ? static_cast<int>(chat_.size()) - maxMessages : 0;
    for (int i = start; i < static_cast<int>(chat_.size()); ++i) {
        const auto& msg = chat_[i];
        const std::string line = (msg.role == "user" ? "You: " : "Gumbo: ") + msg.text;
        DrawText(line.c_str(), static_cast<int>(layout.conversation.x) + 12, y, 18,
                 msg.role == "user" ? SKYBLUE : LIGHTGRAY);
        y += 24;
    }

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
