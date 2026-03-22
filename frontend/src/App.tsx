import { useEffect, useMemo, useRef, useState } from 'react';
import { api } from './lib/api';
import type { Bootstrap, Chat, Message, Project, RunRecord, SecurityFinding, Settings } from './lib/types';
import './styles.css';

declare global {
  interface Window {
    webkitSpeechRecognition?: new () => SpeechRecognition;
    SpeechRecognition?: new () => SpeechRecognition;
  }

  interface SpeechRecognition extends EventTarget {
    continuous: boolean;
    interimResults: boolean;
    lang: string;
    start(): void;
    stop(): void;
    onresult: ((event: SpeechRecognitionEvent) => void) | null;
    onerror: ((event: Event) => void) | null;
    onend: (() => void) | null;
  }

  interface SpeechRecognitionEvent extends Event {
    results: SpeechRecognitionResultList;
  }
}

const NAV_ITEMS = [
  { key: 'chats', label: 'All Chats' },
  { key: 'projects', label: 'Projects' },
  { key: 'security', label: 'Security' },
  { key: 'history', label: 'History' },
  { key: 'settings', label: 'Settings' },
] as const;

type NavKey = (typeof NAV_ITEMS)[number]['key'];

export default function App() {
  const [bootstrap, setBootstrap] = useState<Bootstrap | null>(null);
  const [settings, setSettings] = useState<Settings | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [chats, setChats] = useState<Chat[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [history, setHistory] = useState<RunRecord[]>([]);
  const [findings, setFindings] = useState<SecurityFinding[]>([]);
  const [selectedNav, setSelectedNav] = useState<NavKey>('chats');
  const [selectedChatId, setSelectedChatId] = useState<string>('');
  const [composer, setComposer] = useState('');
  const [targetDirectory, setTargetDirectory] = useState('');
  const [currentUrl, setCurrentUrl] = useState('https://www.framer.com/');
  const [activeRun, setActiveRun] = useState<RunRecord['plan'] | null>(null);
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [approved, setApproved] = useState(false);
  const [logs, setLogs] = useState<Array<Record<string, unknown>>>([]);
  const [summary, setSummary] = useState<RunRecord['execution_summary'] | null>(null);
  const [statusMessage, setStatusMessage] = useState('Loading local agent…');
  const [drawerTab, setDrawerTab] = useState<'plan' | 'logs' | 'findings' | 'settings'>('plan');
  const [isSending, setIsSending] = useState(false);
  const [isExecuting, setIsExecuting] = useState(false);
  const [voiceState, setVoiceState] = useState<'idle' | 'listening' | 'processing' | 'ready' | 'failed'>('idle');
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  const selectedChat = useMemo(() => chats.find((chat) => chat.id === selectedChatId) ?? null, [chats, selectedChatId]);
  const selectedProject = useMemo(() => projects.find((project) => project.id === selectedChat?.project_id) ?? null, [projects, selectedChat]);
  const chatGroups = useMemo(() => {
    const byProject = new Map<string, Chat[]>();
    chats.forEach((chat) => {
      const key = chat.project_id ?? 'ungrouped';
      byProject.set(key, [...(byProject.get(key) ?? []), chat]);
    });
    return byProject;
  }, [chats]);

  useEffect(() => {
    void loadBootstrap();
  }, []);

  useEffect(() => {
    if (selectedChatId) {
      void loadMessages(selectedChatId);
    }
  }, [selectedChatId]);

  async function loadBootstrap() {
    const data = await api.bootstrap();
    setBootstrap(data);
    setSettings(data.settings);
    setProjects(data.projects);
    setChats(data.chats);
    setFindings(data.security.findings);
    setTargetDirectory(data.demo_paths.inbox ?? '');
    const initialChat = data.chats[0]?.id ?? '';
    setSelectedChatId(initialChat);
    setComposer(data.sample_prompts[2] ?? 'Research how Framer localization works, then inspect my current Framer editor and suggest the next steps.');
    setStatusMessage('ComputerAgent is ready. Your data stays on-device.');
    const historyData = await api.history();
    setHistory(historyData.runs);
  }

  async function loadMessages(chatId: string) {
    const response = await api.messages(chatId);
    setMessages(response.messages);
  }

  async function handleSend() {
    if (!selectedChatId || !composer.trim()) return;
    setIsSending(true);
    setApproved(false);
    setSummary(null);
    setLogs([]);
    setStatusMessage('The unified local agent is interpreting your request…');
    try {
      const response = await api.sendMessage({
        chat_id: selectedChatId,
        project_id: selectedProject?.id,
        content: composer,
        current_url: currentUrl,
        target_directory: targetDirectory,
      });
      setComposer('');
      setActiveRun(response.plan);
      setActiveRunId(response.run_id);
      setDrawerTab('plan');
      setStatusMessage(`Plan ready for review. Intent detected: ${response.intent}.`);
      await loadMessages(selectedChatId);
      const historyData = await api.history();
      setHistory(historyData.runs);
      const findingsData = await api.findings();
      setFindings(findingsData.findings);
    } catch (error) {
      setStatusMessage(`Could not process your message: ${(error as Error).message}`);
    } finally {
      setIsSending(false);
    }
  }

  async function handleExecute() {
    if (!activeRunId || !settings) return;
    setIsExecuting(true);
    setStatusMessage('Executing locally with safety controls and audit logging…');
    try {
      const response = await api.execute({ run_id: activeRunId, approved, dry_run: settings.default_dry_run });
      setSummary(response.summary ?? null);
      setLogs(response.logs);
      setFindings((current) => [...response.findings, ...current]);
      setDrawerTab('logs');
      setStatusMessage(response.summary?.message ?? 'Execution completed.');
      await loadMessages(selectedChatId);
      const historyData = await api.history();
      setHistory(historyData.runs);
    } catch (error) {
      setStatusMessage(`Execution failed: ${(error as Error).message}`);
    } finally {
      setIsExecuting(false);
    }
  }

  async function handleRollback() {
    if (!activeRunId) return;
    const response = await api.rollback(activeRunId);
    setStatusMessage(response.messages.join(' ') || 'Rollback completed.');
    const historyData = await api.history();
    setHistory(historyData.runs);
  }

  async function handleQuickScan() {
    const scanTargets = [targetDirectory || bootstrap?.demo_paths.downloads || ''].filter(Boolean);
    const response = await api.quickScan(scanTargets);
    setFindings(response.findings);
    setDrawerTab('findings');
    setStatusMessage(`Quick scan completed with ${response.findings.length} findings.`);
  }

  async function handleStartMonitor() {
    if (!bootstrap?.demo_paths.downloads) return;
    const monitor = await api.startMonitor(bootstrap.demo_paths.downloads);
    setStatusMessage(`Live monitor started for ${String(monitor.folder_path)}.`);
  }

  async function createProject() {
    const name = window.prompt('Project name', 'New project');
    if (!name) return;
    const project = await api.createProject({ name, description: 'Created from the desktop app.', approved_directories: [targetDirectory].filter(Boolean) }).then((result) => result.project);
    setProjects((current) => [...current, project]);
  }

  async function createChat(projectId?: string | null) {
    const title = window.prompt('Chat title', 'New chat');
    if (!title) return;
    const chat = await api.createChat({ title, project_id: projectId }).then((result) => result.chat);
    setChats((current) => [chat, ...current]);
    setSelectedChatId(chat.id);
    setSelectedNav('chats');
  }

  async function saveSettings() {
    if (!settings) return;
    const saved = await api.saveSettings(settings);
    setSettings(saved);
    setStatusMessage('Settings saved locally.');
  }

  function toggleVoice() {
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) {
      setVoiceState('failed');
      setStatusMessage('Voice transcription is unavailable in this runtime. You can still type or paste into the composer.');
      return;
    }
    if (!recognitionRef.current) {
      const recognition = new Recognition();
      recognition.continuous = false;
      recognition.interimResults = true;
      recognition.lang = 'en-US';
      recognition.onresult = (event) => {
        setVoiceState('processing');
        const transcript = Array.from(event.results as any)
          .map((result: any) => result[0]?.transcript ?? '')
          .join(' ')
          .trim();
        setComposer((current) => `${current}${current ? ' ' : ''}${transcript}`.trim());
        setVoiceState('ready');
      };
      recognition.onerror = () => {
        setVoiceState('failed');
        setStatusMessage('Voice transcription failed. Please try again or type manually.');
      };
      recognition.onend = () => {
        setVoiceState((current) => (current === 'processing' ? 'ready' : current === 'failed' ? 'failed' : 'idle'));
      };
      recognitionRef.current = recognition;
    }

    if (voiceState === 'listening') {
      recognitionRef.current.stop();
      setVoiceState('processing');
      return;
    }
    setVoiceState('listening');
    recognitionRef.current.start();
  }

  if (!bootstrap || !settings) {
    return <div className="app-loading">Launching ComputerAgent…</div>;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-panel">
          <button className="brand-badge">CA</button>
          <div>
            <h1>ComputerAgent</h1>
            <p>Your desktop, fully automated.</p>
          </div>
        </div>

        <button className="primary-button full-width" onClick={() => void createChat(selectedProject?.id)}>+ New Chat</button>
        <button className="ghost-button full-width" onClick={() => void createProject()}>+ New Project</button>

        <nav className="nav-stack">
          {NAV_ITEMS.map((item) => (
            <button key={item.key} className={`nav-item ${selectedNav === item.key ? 'active' : ''}`} onClick={() => setSelectedNav(item.key)}>
              {item.label}
            </button>
          ))}
        </nav>

        <div className="sidebar-section">
          <div className="sidebar-title-row">
            <h2>Projects</h2>
          </div>
          {projects.map((project) => (
            <div key={project.id} className="project-card">
              <button className="project-name" onClick={() => void createChat(project.id)}>{project.name}</button>
              <p>{project.description}</p>
              <div className="project-chats">
                {(chatGroups.get(project.id) ?? []).map((chat) => (
                  <button key={chat.id} className={`chat-pill ${selectedChatId === chat.id ? 'active' : ''}`} onClick={() => { setSelectedChatId(chat.id); setSelectedNav('chats'); }}>
                    {chat.title}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>

        <div className="sidebar-section">
          <h2>Unattached chats</h2>
          {(chatGroups.get('ungrouped') ?? []).map((chat) => (
            <button key={chat.id} className={`chat-row ${selectedChatId === chat.id ? 'active' : ''}`} onClick={() => { setSelectedChatId(chat.id); setSelectedNav('chats'); }}>
              {chat.title}
            </button>
          ))}
        </div>
      </aside>

      <main className="main-layout">
        <header className="topbar">
          <div>
            <h2>{selectedProject?.name ?? 'General workspace'}</h2>
            <p>{statusMessage}</p>
          </div>
          <div className="topbar-pills">
            <span className="pill secondary">Unified local agent</span>
            <span className="pill">Mode: {settings.planner_mode}</span>
            <span className="pill">Voice: {voiceState}</span>
          </div>
        </header>

        <section className="workspace">
          <div className="chat-column card">
            {selectedNav === 'chats' || selectedNav === 'projects' ? (
              <>
                <div className="chat-thread">
                  {messages.map((message) => (
                    <article key={message.id} className={`message ${message.role}`}>
                      <div className="message-role">{message.role === 'assistant' ? 'ComputerAgent' : message.role === 'user' ? 'You' : 'System'}</div>
                      <div className="message-body">
                        <p>{message.content}</p>
                        {message.sources.length > 0 ? (
                          <div className="message-meta">
                            {message.sources.map((source) => (
                              <div key={`${source.domain}-${source.title}`} className="source-card">
                                <strong>{source.title}</strong>
                                <span>{source.domain}</span>
                                <p>{source.summary}</p>
                              </div>
                            ))}
                          </div>
                        ) : null}
                        {message.findings.length > 0 ? (
                          <div className="finding-strip">
                            {message.findings.map((finding) => (
                              <div key={finding.id} className={`finding-pill ${finding.severity}`}>{finding.title}</div>
                            ))}
                          </div>
                        ) : null}
                      </div>
                    </article>
                  ))}
                  {messages.length === 0 ? (
                    <div className="empty-chat">
                      <h3>Plan your workflow</h3>
                      <p>Ask one shared agent to research docs, inspect web apps, manage files, or run defensive scans.</p>
                      <div className="sample-grid">
                        {bootstrap.sample_prompts.map((prompt) => (
                          <button key={prompt} className="sample-card" onClick={() => setComposer(prompt)}>{prompt}</button>
                        ))}
                      </div>
                    </div>
                  ) : null}
                </div>

                <div className="composer-card">
                  <div className="composer-controls">
                    <input value={targetDirectory} onChange={(event) => setTargetDirectory(event.target.value)} placeholder="Approved target directory" />
                    <input value={currentUrl} onChange={(event) => setCurrentUrl(event.target.value)} placeholder="Current browser URL (optional)" />
                  </div>
                  <textarea
                    value={composer}
                    onChange={(event) => setComposer(event.target.value)}
                    rows={4}
                    placeholder="Ask ComputerAgent anything: research, inspect, plan, execute, or monitor."
                    onKeyDown={(event) => {
                      if (event.key === 'Enter' && !event.shiftKey) {
                        event.preventDefault();
                        void handleSend();
                      }
                    }}
                  />
                  <div className="composer-footer">
                    <div className="composer-hints">
                      <span className="pill">Enter to send</span>
                      <span className="pill">Shift+Enter for newline</span>
                      <span className="pill secondary">Your data stays on-device</span>
                    </div>
                    <div className="composer-actions">
                      <button className={`ghost-button ${voiceState === 'listening' ? 'recording' : ''}`} onClick={toggleVoice}>🎙 {voiceState === 'listening' ? 'Listening' : 'Voice'}</button>
                      <button className="primary-button" onClick={() => void handleSend()} disabled={isSending || !composer.trim()}>{isSending ? 'Thinking…' : 'Send'}</button>
                    </div>
                  </div>
                </div>
              </>
            ) : null}

            {selectedNav === 'security' ? (
              <section className="security-view">
                <div className="security-header">
                  <div>
                    <h3>Defensive local security</h3>
                    <p>Quick scans, background monitoring, quarantine-ready findings, and plain-English reporting.</p>
                  </div>
                  <div className="security-actions">
                    <button className="secondary-button" onClick={() => void handleQuickScan()}>Quick Scan</button>
                    <button className="ghost-button" onClick={() => void handleStartMonitor()}>Start Live Monitor</button>
                  </div>
                </div>
                <div className="finding-list">
                  {findings.map((finding) => (
                    <article key={finding.id} className={`finding-card severity-${finding.severity}`}>
                      <div className="finding-topline">
                        <strong>{finding.title}</strong>
                        <span>{finding.severity} • {Math.round(finding.confidence * 100)}%</span>
                      </div>
                      <p>{finding.affected_path_or_process}</p>
                      <ul>
                        {finding.evidence.map((item) => <li key={item}>{item}</li>)}
                      </ul>
                      <p className="muted">Recommended action: {finding.recommended_action}</p>
                    </article>
                  ))}
                  {findings.length === 0 ? <p className="muted">No security findings yet. Run a quick scan or start a live monitor.</p> : null}
                </div>
              </section>
            ) : null}

            {selectedNav === 'history' ? (
              <section className="history-view">
                <h3>Run history</h3>
                <div className="history-list">
                  {history.map((run) => (
                    <button key={run.run_id} className="history-item" onClick={() => { setActiveRun(run.plan); setActiveRunId(run.run_id); setSummary(run.execution_summary ?? null); setDrawerTab('plan'); }}>
                      <strong>{run.prompt}</strong>
                      <span>{run.status} • {new Date(run.created_at).toLocaleString()}</span>
                    </button>
                  ))}
                </div>
              </section>
            ) : null}

            {selectedNav === 'settings' ? (
              <section className="settings-view">
                <h3>Settings</h3>
                <div className="settings-grid">
                  <label>Planner mode<select value={settings.planner_mode} onChange={(event) => setSettings({ ...settings, planner_mode: event.target.value })}><option value="mock">Mock</option><option value="llm">Local LLM</option></select></label>
                  <label>Browser mode<select value={settings.browser_mode} onChange={(event) => setSettings({ ...settings, browser_mode: event.target.value })}><option value="headed">Headed</option><option value="headless">Headless</option></select></label>
                  <label>Preferred docs domains<textarea value={settings.preferred_docs_domains.join('\n')} onChange={(event) => setSettings({ ...settings, preferred_docs_domains: event.target.value.split('\n').filter(Boolean) })} /></label>
                  <label>Allowed directories<textarea value={settings.allowed_directories.join('\n')} onChange={(event) => setSettings({ ...settings, allowed_directories: event.target.value.split('\n').filter(Boolean) })} /></label>
                  <label>Watched folders<textarea value={settings.security_watched_folders.join('\n')} onChange={(event) => setSettings({ ...settings, security_watched_folders: event.target.value.split('\n').filter(Boolean) })} /></label>
                  <label>Max background jobs<input type="number" value={settings.maximum_concurrent_background_jobs} onChange={(event) => setSettings({ ...settings, maximum_concurrent_background_jobs: Number(event.target.value) })} /></label>
                </div>
                <div className="toggle-list">
                  <label><input type="checkbox" checked={settings.docs_research_enabled} onChange={(event) => setSettings({ ...settings, docs_research_enabled: event.target.checked })} /> Docs research enabled</label>
                  <label><input type="checkbox" checked={settings.browser_automation_enabled} onChange={(event) => setSettings({ ...settings, browser_automation_enabled: event.target.checked })} /> Browser automation enabled</label>
                  <label><input type="checkbox" checked={settings.project_memory_enabled} onChange={(event) => setSettings({ ...settings, project_memory_enabled: event.target.checked })} /> Project memory enabled</label>
                  <label><input type="checkbox" checked={settings.require_approval_before_foreground_control} onChange={(event) => setSettings({ ...settings, require_approval_before_foreground_control: event.target.checked })} /> Require approval before foreground control</label>
                  <label><input type="checkbox" checked={settings.default_dry_run} onChange={(event) => setSettings({ ...settings, default_dry_run: event.target.checked })} /> Default to dry run</label>
                </div>
                <button className="primary-button" onClick={() => void saveSettings()}>Save settings</button>
              </section>
            ) : null}
          </div>

          <aside className="drawer card">
            <div className="drawer-tabs">
              <button className={drawerTab === 'plan' ? 'active' : ''} onClick={() => setDrawerTab('plan')}>Plan</button>
              <button className={drawerTab === 'logs' ? 'active' : ''} onClick={() => setDrawerTab('logs')}>Logs</button>
              <button className={drawerTab === 'findings' ? 'active' : ''} onClick={() => setDrawerTab('findings')}>Findings</button>
              <button className={drawerTab === 'settings' ? 'active' : ''} onClick={() => setDrawerTab('settings')}>Summary</button>
            </div>

            {drawerTab === 'plan' ? (
              <div className="drawer-content">
                <h3>Approval-ready plan</h3>
                {!activeRun ? <p className="muted">Send a chat message to generate a unified plan.</p> : null}
                {activeRun?.actions.map((action) => (
                  <article key={action.id} className="action-card">
                    <div className="action-topline">
                      <strong>{action.description}</strong>
                      <span className={`lane-pill ${action.execution_lane}`}>{action.execution_lane.replace('_', ' ')}</span>
                    </div>
                    <div className="meta-row">
                      <span>{action.type}</span>
                      <span>{action.target_app}</span>
                      <span>{Math.round(action.confidence * 100)}% confidence</span>
                    </div>
                    <pre>{JSON.stringify(action.params, null, 2)}</pre>
                  </article>
                ))}
                {activeRun ? (
                  <>
                    <div className="validation-box">
                      <strong>{activeRun.validation.allowed ? 'Ready for approval' : 'Blocked by policy'}</strong>
                      {activeRun.validation.issues.map((issue) => <p key={`${issue.level}-${issue.message}`}>{issue.level.toUpperCase()}: {issue.message}</p>)}
                    </div>
                    <label className="approval-row"><input type="checkbox" checked={approved} onChange={(event) => setApproved(event.target.checked)} /> I approve this plan.</label>
                    <div className="button-row">
                      <button className="secondary-button" onClick={() => void handleExecute()} disabled={!approved || !activeRun.validation.allowed || isExecuting}>{isExecuting ? 'Executing…' : settings.default_dry_run ? 'Dry Run Execute' : 'Execute'}</button>
                      <button className="ghost-button" onClick={() => void handleRollback()} disabled={!summary?.rollback_available}>Rollback</button>
                    </div>
                  </>
                ) : null}
              </div>
            ) : null}

            {drawerTab === 'logs' ? (
              <div className="drawer-content log-panel">
                <h3>Audit logs</h3>
                {logs.length === 0 ? <p className="muted">No logs yet.</p> : null}
                {logs.map((log, index) => <pre key={index}>{JSON.stringify(log, null, 2)}</pre>)}
              </div>
            ) : null}

            {drawerTab === 'findings' ? (
              <div className="drawer-content">
                <h3>Research and security findings</h3>
                {activeRun?.sources.map((source) => (
                  <article key={source.title} className="source-card large">
                    <strong>{source.title}</strong>
                    <span>{source.domain}</span>
                    <p>{source.summary}</p>
                  </article>
                ))}
                {findings.map((finding) => (
                  <article key={finding.id} className={`finding-card compact severity-${finding.severity}`}>
                    <strong>{finding.title}</strong>
                    <p>{finding.affected_path_or_process}</p>
                  </article>
                ))}
              </div>
            ) : null}

            {drawerTab === 'settings' ? (
              <div className="drawer-content">
                <h3>Execution summary</h3>
                {!summary ? <p className="muted">No execution summary yet.</p> : null}
                {summary ? (
                  <>
                    <p><strong>Status:</strong> {summary.success ? 'Success' : 'Needs review'}</p>
                    <p><strong>Lane usage:</strong> {summary.lane_usage.join(', ')}</p>
                    <p>{summary.high_level_result}</p>
                    <div className="summary-chips">
                      {summary.highlights.map((line) => <span key={line} className="pill">{line}</span>)}
                    </div>
                  </>
                ) : null}
              </div>
            ) : null}
          </aside>
        </section>
      </main>
    </div>
  );
}
