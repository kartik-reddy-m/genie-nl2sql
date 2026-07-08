import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { format as formatSql } from "sql-formatter";
import {
  startConversation,
  sendFollowUp,
  listConversations,
  getConversation,
  deleteConversation,
  setOnAuthExpired,
} from "./api.js";
import {
  authEnabled,
  GOOGLE_CLIENT_ID,
  getUser,
  setToken,
  signOut,
} from "./auth.js";
import ResultTable from "./ResultTable.jsx";

function prettySql(sql) {
  try {
    return formatSql(sql, { language: "spark", keywordCase: "upper" });
  } catch {
    return sql; // fall back to the raw SQL if formatting fails
  }
}

export default function App() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]); // {role, text, sql, result, error, status}
  const [busy, setBusy] = useState(false);
  const [conversationId, setConversationId] = useState(null);
  const [history, setHistory] = useState([]);
  const [user, setUser] = useState(getUser());
  const [sidebarOpen, setSidebarOpen] = useState(true);

  async function loadHistory() {
    try {
      setHistory(await listConversations());
    } catch {
      /* history is best-effort; ignore load errors */
    }
  }

  // When a request 401s, drop back to the login screen.
  useEffect(() => {
    setOnAuthExpired(() => setUser(null));
  }, []);

  useEffect(() => {
    if (authEnabled && !user) return; // wait until signed in
    loadHistory();
  }, [user]);

  if (authEnabled && !user) {
    return <LoginGate onSignedIn={() => setUser(getUser())} />;
  }

  function pushMessage(msg) {
    setMessages((prev) => [...prev, msg]);
  }

  function updateLast(patch) {
    setMessages((prev) => {
      const next = [...prev];
      next[next.length - 1] = { ...next[next.length - 1], ...patch };
      return next;
    });
  }

  async function ask() {
    const q = question.trim();
    if (!q || busy) return;

    setBusy(true);
    setQuestion("");
    pushMessage({ role: "user", text: q });
    pushMessage({ role: "assistant", status: "WORKING" });

    try {
      const final = conversationId
        ? await sendFollowUp(conversationId, q)
        : await startConversation(q);

      setConversationId(final.conversation_id);

      if (final.status === "FAILED") {
        updateLast({ status: final.status, error: final.error || "Failed." });
      } else {
        updateLast({
          status: final.status,
          text: final.answer_text,
          sql: final.sql,
          result: final.result,
          error: final.error,
        });
      }
      loadHistory();
    } catch (err) {
      updateLast({ status: "ERROR", error: String(err.message || err) });
    } finally {
      setBusy(false);
    }
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      ask();
    }
  }

  function newConversation() {
    setConversationId(null);
    setMessages([]);
    setQuestion("");
  }

  async function openConversation(id) {
    if (busy) return;
    try {
      const conv = await getConversation(id);
      setMessages(conv.messages || []);
      setConversationId(conv.id);
    } catch (err) {
      alert("Could not load conversation: " + (err.message || err));
    }
  }

  async function removeConversation(id, e) {
    e.stopPropagation();
    if (!confirm("Delete this conversation?")) return;
    try {
      await deleteConversation(id);
      if (id === conversationId) newConversation();
      loadHistory();
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="layout">
      <aside className={"sidebar" + (sidebarOpen ? "" : " collapsed")}>
        <div className="sidebar-header">
          <span>History</span>
          <button className="new-btn" onClick={newConversation} disabled={busy}>
            + New
          </button>
        </div>
        <div className="history-list">
          {history.length === 0 && (
            <div className="history-empty">No conversations yet</div>
          )}
          {history.map((h) => (
            <div
              key={h.id}
              className={
                "history-item" + (h.id === conversationId ? " active" : "")
              }
              onClick={() => openConversation(h.id)}
              title={h.title}
            >
              <div className="history-title">{h.title || "Untitled"}</div>
              <div className="history-meta">
                {Math.floor((h.message_count || 0) / 2)} Q · {formatTime(h.updated_at)}
              </div>
              <button
                className="history-del"
                title="Delete"
                onClick={(e) => removeConversation(h.id, e)}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </aside>

      <div className="app">
        <header className="header">
          <button
            className="sidebar-toggle"
            onClick={() => setSidebarOpen((o) => !o)}
            title={sidebarOpen ? "Hide history" : "Show history"}
            aria-label="Toggle history"
          >
            ☰
          </button>
          <h1>Ask Mits AI</h1>
          <p>Ask a question in plain English. Databricks Genie writes the SQL and returns the data.</p>
          {authEnabled && user && (
            <div className="user-chip">
              {user.picture && <img src={user.picture} alt="" />}
              <span className="user-email">{user.email}</span>
              <button
                className="signout"
                onClick={() => {
                  signOut();
                  setUser(null);
                }}
              >
                Sign out
              </button>
            </div>
          )}
        </header>

        <main className="chat">
          {messages.length === 0 && (
            <div className="empty">Try: “Show total sales by region for last quarter.”</div>
          )}
          {messages.map((m, i) => (
            <Bubble key={i} m={m} />
          ))}
        </main>

        <footer className="composer">
          <textarea
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={onKeyDown}
            placeholder="Ask a question…"
            rows={2}
            disabled={busy}
          />
          <button onClick={ask} disabled={busy || !question.trim()}>
            {busy ? "Working…" : "Ask"}
          </button>
        </footer>
      </div>
    </div>
  );
}

function Bubble({ m }) {
  if (m.role === "user") {
    return (
      <div className="bubble user">
        <div className="text">{m.text}</div>
      </div>
    );
  }

  const pending = !m.text && !m.error && !m.result;

  return (
    <div className="bubble assistant">
      {pending && (
        <div className="status">
          <span className="spinner" /> {prettyStatus(m.status)}
        </div>
      )}

      {m.error && <div className="error">⚠ {m.error}</div>}

      {m.text && (
        <div className="text markdown">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.text}</ReactMarkdown>
        </div>
      )}

      {m.result && <ResultTable result={m.result} />}

      {m.sql && (
        <details className="sql">
          <summary>Show SQL</summary>
          <pre>{prettySql(m.sql)}</pre>
        </details>
      )}
    </div>
  );
}

function prettyStatus(status) {
  const map = {
    WORKING: "Generating SQL and running query…",
    COMPLETED: "Done",
  };
  return map[status] || status || "Working…";
}

function formatTime(epoch) {
  if (!epoch) return "";
  const d = new Date(epoch * 1000);
  const now = new Date();
  const sameDay = d.toDateString() === now.toDateString();
  return sameDay
    ? d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
    : d.toLocaleDateString([], { month: "short", day: "numeric" });
}

function LoginGate({ onSignedIn }) {
  useEffect(() => {
    let cancelled = false;
    function init() {
      if (cancelled) return;
      const g = window.google;
      if (!g?.accounts?.id) {
        setTimeout(init, 200); // GIS script still loading
        return;
      }
      g.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: (resp) => {
          if (resp?.credential) {
            setToken(resp.credential);
            onSignedIn();
          }
        },
      });
      const el = document.getElementById("gbtn");
      if (el) {
        g.accounts.id.renderButton(el, {
          theme: "filled_blue",
          size: "large",
          text: "signin_with",
          shape: "pill",
        });
      }
    }
    init();
    return () => {
      cancelled = true;
    };
  }, [onSignedIn]);

  return (
    <div className="login">
      <div className="login-card">
        <h1>Ask Mits AI</h1>
        <p>Sign in with Google to continue.</p>
        <div id="gbtn" className="gbtn" />
      </div>
    </div>
  );
}
