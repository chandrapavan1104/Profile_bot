import React, { useState, useRef, useEffect } from "react";
import { Container, Row, Col, Form, Button, Spinner } from "react-bootstrap";
import ReactMarkdown from "react-markdown";
import portfolio from "../../Portfolio";

const CHAT_HISTORY_KEY = "chatbotMessages";
const DEFAULT_ASSISTANT_MESSAGE = {
  role: "assistant",
  content:
    "Hi there! I'm Chandra Pavan's AI assistant. Ask me anything about his experience, skills, or projects.",
};

function Chatbot() {
  const apiUrl = import.meta.env.VITE_CHATBOT_API_URL ||
  "https://profile-bot-api-usc-977721269659.us-central1.run.app/ask";
  const streamUrl = apiUrl.endsWith("/ask") ? `${apiUrl}/stream` : apiUrl;
  const [messages, setMessages] = useState(() => {
    if (typeof window === "undefined") {
      return [DEFAULT_ASSISTANT_MESSAGE];
    }

    try {
      const stored = sessionStorage.getItem(CHAT_HISTORY_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed) && parsed.length > 0) {
          return parsed;
        }
      }
    } catch {
      // Ignore storage errors and fall back to default messages.
    }

    return [DEFAULT_ASSISTANT_MESSAGE];
  });
  const [input, setInput] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const endOfChatRef = useRef(null);
  const firstName = portfolio.name?.split(" ")[0] || "You";

  useEffect(() => {
    endOfChatRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const appendAssistantContent = (chunk) => {
    if (!chunk) {
      return;
    }

    setMessages((prev) => {
      if (!prev.length) {
        return prev;
      }
      const next = [...prev];
      const lastIndex = next.length - 1;
      if (next[lastIndex].role !== "assistant") {
        return next;
      }
      next[lastIndex] = {
        ...next[lastIndex],
        content: `${next[lastIndex].content}${chunk}`,
      };
      return next;
    });
  };

  const parseSseEventData = (event) => {
    const lines = event.split(/\r?\n/);
    const dataLines = [];

    for (const line of lines) {
      if (line.startsWith("data:")) {
        dataLines.push(line.replace(/^data:\s?/, ""));
      } else if (line.trim() !== "") {
        dataLines.push(line);
      }
    }

    if (!dataLines.length) {
      return null;
    }

    return dataLines.join("\n");
  };

  const replaceAssistantContent = (content) => {
    setMessages((prev) => {
      if (!prev.length) {
        return prev;
      }
      const next = [...prev];
      const lastIndex = next.length - 1;
      if (next[lastIndex].role !== "assistant") {
        return next;
      }
      next[lastIndex] = {
        ...next[lastIndex],
        content,
      };
      return next;
    });
  };

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    try {
      sessionStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(messages));
    } catch {
      // Ignore storage errors.
    }
  }, [messages]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    const query = input.trim();
    if (!query) {
      return;
    }

    const historyMessages = messages;
    const userMessage = { role: "user", content: query };
    setMessages((prev) => [...prev, userMessage, { role: "assistant", content: "" }]);
    setInput("");
    setIsSubmitting(true);

    try {
      const payload = { query, messages: historyMessages };
      if (sessionId) {
        payload.session_id = sessionId;
      }

      const response = await fetch(streamUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Accept: "text/event-stream",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const contentType = response.headers.get("content-type") || "";
      if (!response.body || contentType.includes("application/json")) {
        const data = await response.json();
        if (data?.session_id) {
          setSessionId(data.session_id);
        }
        const answer =
          data?.answer ||
          data?.response ||
          "I'm not sure how to answer that yet, but Chandra keeps teaching me new things!";
        replaceAssistantContent(answer);
        return;
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let doneStreaming = false;

      while (!doneStreaming) {
        const { value, done } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop() || "";

        for (const event of events) {
          const data = parseSseEventData(event);
          if (!data) {
            continue;
          }
          if (data === "[DONE]") {
            doneStreaming = true;
            break;
          }
          appendAssistantContent(data);
        }
      }
    } catch (error) {
      replaceAssistantContent(
        "Sorry, I ran into a hiccup while fetching the answer. Please try asking again in a moment."
      );
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <section className="chatbot-section">
      <Container fluid className="chatbot-container">
        <Row className="justify-content-center chatbot-row">
          <Col lg={12} className="chatbot-column">
            <div className="chatbot-header">
              <h1>
                Meet <span className="purple">{portfolio.name}</span>&apos;s AI
                Assistant
              </h1>
              <p>
                Curious about my background, skills, or the projects I&apos;ve
                built? Just ask away and the assistant will help you out.
              </p>
            </div>
            <div className="chatbot-window">
              <div className="chatbot-messages">
                {messages.map((message, index) => (
                  <div
                    key={`${message.role}-${index}`}
                    className={`chatbot-message chatbot-message-${message.role}`}
                  >
                    <div className="chatbot-message-label">
                      {message.role === "assistant"
                        ? "Assistant"
                        : firstName}
                    </div>
                    <div className="chatbot-message-content">
                      <ReactMarkdown>{String(message.content)}</ReactMarkdown>
                    </div>
                  </div>
                ))}
                <div ref={endOfChatRef} />
              </div>
              <Form onSubmit={handleSubmit} className="chatbot-form">
                <Form.Control
                  type="text"
                  placeholder="Ask anything about Chandra Pavan..."
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  disabled={isSubmitting}
                />
                <Button
                  type="submit"
                  variant="primary"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? (
                    <>
                      <Spinner
                        animation="border"
                        role="status"
                        size="sm"
                        className="me-2"
                      />
                      Thinking...
                    </>
                  ) : (
                    "Ask"
                  )}
                </Button>
              </Form>
            </div>
          </Col>
        </Row>
      </Container>
    </section>
  );
}

export default Chatbot;
