import React, { useState, useEffect, useRef, useCallback } from 'react';
import { 
  Activity, 
  Settings, 
  Play, 
  Square, 
  RotateCcw, 
  AlertTriangle, 
  ChevronRight, 
  ChevronLeft, 
  ChevronUp, 
  ChevronDown,
  Cpu,
  Database,
  Terminal,
  Camera,
  Layers,
  Download,
  Grid,
  Video
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { SystemState } from './types';
import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

const BUTTON_BASE = "px-4 py-2 rounded-lg font-bold transition-all active:scale-95 disabled:opacity-50 disabled:pointer-events-none";
const BUTTON_PRIMARY = cn(BUTTON_BASE, "bg-hw-accent text-black hover:bg-opacity-90");
const BUTTON_SECONDARY = cn(BUTTON_BASE, "bg-hw-border text-hw-text hover:bg-opacity-80");
const BUTTON_DANGER = cn(BUTTON_BASE, "bg-hw-danger text-white hover:bg-opacity-90");

export default function App() {
  const [state, setState] = useState<SystemState | null>(null);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'debug' | 'results' | 'settings' | 'system'>('dashboard');
  const logEndRef = useRef<HTMLDivElement>(null);

  const fetchState = useCallback(async () => {
    try {
      const res = await fetch('/api/state');
      if (!res.ok) {
        return;
      }
      
      const contentType = res.headers.get('content-type');
      if (!contentType || !contentType.includes('application/json')) {
        return;
      }

      const data = await res.json();
      setState(data);
    } catch (err) {
      // Catch network errors silently until initialized
    }
  }, []);

  useEffect(() => {
    fetchState();
    const interval = setInterval(fetchState, 1000);
    return () => clearInterval(interval);
  }, [fetchState]);

  useEffect(() => {
    logEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [state?.process.logs]);

  const controlGantry = async (x: number, y: number) => {
    await fetch('/api/control/gantry', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ x, y }),
    });
  };

  const controlStirrer = async (active: boolean) => {
    await fetch('/api/control/stirrer', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ active }),
    });
  };

  const controlScoop = async (position: 'up' | 'down') => {
    await fetch('/api/control/scoop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ position }),
    });
  };

  const updateConfig = async (rows: number, cols: number) => {
    await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ rows, cols }),
    });
  };

  const exportResults = async () => {
    const res = await fetch('/api/export', { method: 'POST' });
    if (res.ok) {
      const data = await res.json();
      alert(`Export Successful: ${data.path}`);
    } else {
      alert("Export Failed");
    }
  };

  const resetSystem = async () => {
    await fetch('/api/control/reset', { method: 'POST' });
  };

  const toggleDummyMode = async (enabled: boolean) => {
    await fetch('/api/control/dummy', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    });
  };

  const startProcess = async () => {
    await fetch('/api/control/start', { method: 'POST' });
  };

  const stopProcess = async () => {
    await fetch('/api/control/stop', { method: 'POST' });
  };

  if (!state) return <div className="flex items-center justify-center h-screen bg-hw-bg text-hw-accent font-mono text-xl">INITIALIZING SYSTEM...</div>;

  return (
    <div className="flex flex-col h-screen max-w-7xl mx-auto p-4 gap-4">
      {/* Header */}
      <header className="flex items-center justify-between hw-panel p-4">
        <div className="flex items-center gap-3">
          <div className="bg-hw-accent/10 p-2 rounded-lg">
            <Activity className="text-hw-accent w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight">SoilSense <span className="text-hw-accent">v3.0</span></h1>
            <p className="hw-label m-0">Raspberry Pi Hardware Controller</p>
          </div>
        </div>
        
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-4 mr-4">
            <StatusIndicator label="PYTHON BRIDGE" status={state.pythonBridge === 'online' ? 'connected' : 'disconnected'} />
            <div className="h-4 w-px bg-hw-border mx-1" />
            <StatusIndicator label="JETSON" status={state.jetson?.status ?? 'disconnected'} />
            <StatusIndicator label="GANTRY" status={state.gantry?.status ?? 'disconnected'} />
            <StatusIndicator label="STIR" status={state.stirrer?.status ?? 'disconnected'} />
            <StatusIndicator label="SCOOP" status={state.scoop?.status ?? 'disconnected'} />
          </div>
          <div className="h-8 w-px bg-hw-border" />
          <nav className="flex gap-2">
            <NavButton active={activeTab === 'dashboard'} onClick={() => setActiveTab('dashboard')} icon={<Activity className="w-4 h-4" />} label="DASH" />
            <NavButton active={activeTab === 'results'} onClick={() => setActiveTab('results')} icon={<Database className="w-4 h-4" />} label="RESULTS" />
            <NavButton active={activeTab === 'debug'} onClick={() => setActiveTab('debug')} icon={<Settings className="w-4 h-4" />} label="DEBUG" />
            <NavButton active={activeTab === 'settings'} onClick={() => setActiveTab('settings')} icon={<Grid className="w-4 h-4" />} label="CONFIG" />
            <NavButton active={activeTab === 'system'} onClick={() => setActiveTab('system')} icon={<Terminal className="w-4 h-4" />} label="SYSTEM" />
          </nav>
        </div>
      </header>

      <main className="flex-1 grid grid-cols-12 gap-4 overflow-hidden">
        {/* Left Column: Main View */}
        <div className="col-span-8 flex flex-col gap-4 overflow-hidden">
          <div className="hw-panel flex-1 overflow-hidden flex flex-col">
            <AnimatePresence mode="wait">
              {activeTab === 'dashboard' && (
                <motion.div 
                  key="dash"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="flex-1 p-6 flex flex-col items-center justify-center relative bg-[radial-gradient(circle_at_center,_var(--color-hw-border)_1px,_transparent_1px)] bg-[size:40px_40px]"
                >
                  <div className="hw-label absolute top-4 left-4">Gantry Visualization ({state.config.rows}x{state.config.cols})</div>
                  
                  <div className="relative border-2 border-hw-border p-8 rounded-xl bg-hw-bg/50">
                    <div 
                      className="grid gap-8"
                      style={{ 
                        gridTemplateColumns: `repeat(${state.config.cols}, minmax(0, 1fr))`,
                        gridTemplateRows: `repeat(${state.config.rows}, minmax(0, 1fr))`
                      }}
                    >
                      {Array.from({ length: state.config.rows * state.config.cols }).map((_, i) => {
                        const r = Math.floor(i / state.config.cols);
                        const c = i % state.config.cols;
                        const isActive = state.gantry.x === c * state.config.dist && state.gantry.y === r * state.config.dist;
                        const hasResult = state.process.soilTypes[i] !== null;
                        
                        return (
                          <div 
                            key={i} 
                            className={cn(
                              "w-12 h-12 rounded-full border-2 flex items-center justify-center transition-all duration-500",
                              isActive ? "border-hw-accent bg-hw-accent/20 scale-110 shadow-[0_0_15px_rgba(0,255,65,0.3)]" : "border-hw-border bg-hw-card",
                              hasResult && !isActive ? "bg-hw-accent/10 border-hw-accent/50" : ""
                            )}
                          >
                            <span className="text-[8px] font-mono m-0">{r},{c}</span>
                          </div>
                        );
                      })}
                    </div>

                    {state.config.dist > 0 && (
                      <motion.div 
                        className="absolute w-4 h-4 bg-hw-accent rounded-full shadow-[0_0_10px_#00ff41] z-10"
                        animate={{ 
                          x: (state.gantry.x / state.config.dist) * 80 + 32, // Adjusted for smaller dots
                          y: (state.gantry.y / state.config.dist) * 80 + 32 
                        }}
                        transition={{ type: 'spring', stiffness: 50, damping: 15 }}
                      />
                    )}
                  </div>
                </motion.div>
              )}

              {activeTab === 'results' && (
                <motion.div 
                  key="results"
                  initial={{ opacity: 0, x: 20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -20 }}
                  className="flex-1 p-6 overflow-y-auto"
                >
                  <div className="flex items-center justify-between mb-6">
                    <div className="hw-label">Soil Analysis Results</div>
                    <button onClick={exportResults} className={cn(BUTTON_PRIMARY, "flex items-center gap-2")}>
                      <Download className="w-4 h-4" /> EXPORT TO SD/USB
                    </button>
                  </div>
                  
                  <div className="grid grid-cols-4 gap-4">
                    {state.process.soilTypes.map((type, i) => (
                      <div key={i} className="hw-panel p-3 border-hw-accent/20">
                        <div className="hw-label text-[8px]">BAG {Math.floor(i / state.config.cols)},{i % state.config.cols}</div>
                        <div className={cn("text-lg font-mono", type ? "text-hw-accent" : "text-hw-text-dim italic")}>
                          {type || "PENDING"}
                        </div>
                      </div>
                    ))}
                  </div>
                </motion.div>
              )}

              {activeTab === 'debug' && (
                <motion.div 
                  key="debug"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex-1 p-6 grid grid-cols-2 gap-6 overflow-y-auto"
                >
                  <div className="hw-label col-span-2">Manual Debug Controls</div>
                  
                  <DebugPanel title="System Mode" icon={<Cpu className="w-4 h-4 text-hw-accent" />}>
                    <div className="flex items-center justify-between p-2 bg-hw-bg/50 rounded-lg">
                      <div className="flex flex-col">
                        <span className="text-sm font-bold">Dummy Mode</span>
                        <span className="text-[10px] text-hw-text-dim">Simulate hardware for testing</span>
                      </div>
                      <button 
                        onClick={() => toggleDummyMode(!state.dummyMode)}
                        className={cn(
                          "w-12 h-6 rounded-full relative transition-colors",
                          state.dummyMode ? "bg-hw-accent" : "bg-hw-border"
                        )}
                      >
                        <motion.div 
                          className="absolute top-1 left-1 w-4 h-4 bg-white rounded-full"
                          animate={{ x: state.dummyMode ? 24 : 0 }}
                        />
                      </button>
                    </div>
                  </DebugPanel>

                  <DebugPanel title="Gantry (X,Y)" icon={<Layers className="w-4 h-4 text-hw-accent" />}>
                    <div className="grid grid-cols-3 gap-2 max-w-[150px] mx-auto">
                      <div /><DebugButton icon={<ChevronUp />} onClick={() => controlGantry(state.gantry.x, Math.max(0, state.gantry.y - 5))} /><div />
                      <DebugButton icon={<ChevronLeft />} onClick={() => controlGantry(Math.max(0, state.gantry.x - 5), state.gantry.y)} />
                      <div className="bg-hw-border rounded-lg flex items-center justify-center text-[10px] font-mono">MOVE</div>
                      <DebugButton icon={<ChevronRight />} onClick={() => controlGantry(state.gantry.x + 5, state.gantry.y)} />
                      <div /><DebugButton icon={<ChevronDown />} onClick={() => controlGantry(state.gantry.x, state.gantry.y + 5)} /><div />
                    </div>
                  </DebugPanel>
                  <DebugPanel title="Stirrer Motor" icon={<RotateCcw className="w-4 h-4 text-hw-accent" />}>
                    <button 
                      onClick={() => controlStirrer(!state.stirrer.active)}
                      className={cn(BUTTON_BASE, "w-full h-16 text-lg", state.stirrer.active ? "bg-hw-danger text-white" : "bg-hw-accent text-black")}
                    >
                      {state.stirrer.active ? "STOP STIRRER" : "START STIRRER"}
                    </button>
                  </DebugPanel>
                  <DebugPanel title="Scoop Actuator" icon={<Database className="w-4 h-4 text-hw-accent" />}>
                    <div className="grid grid-cols-2 gap-2">
                      <button onClick={() => controlScoop('down')} className={cn(BUTTON_BASE, "h-16", state.scoop.position === 'down' ? "bg-hw-accent text-black" : "bg-hw-border")}>LOWER</button>
                      <button onClick={() => controlScoop('up')} className={cn(BUTTON_BASE, "h-16", state.scoop.position === 'up' ? "bg-hw-accent text-black" : "bg-hw-border")}>RAISE</button>
                    </div>
                  </DebugPanel>
                  <DebugPanel title="Camera / Analysis" icon={<Camera className="w-4 h-4 text-hw-accent" />}>
                    <button className={cn(BUTTON_SECONDARY, "w-full h-16 flex items-center justify-center gap-2")}>
                      <Camera className="w-5 h-5" /> CAPTURE TEST
                    </button>
                  </DebugPanel>
                </motion.div>
              )}

              {activeTab === 'settings' && (
                <motion.div 
                  key="settings"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex-1 p-6"
                >
                  <div className="hw-label mb-6">Grid Configuration</div>
                  <div className="grid grid-cols-2 gap-8 max-w-md">
                    <div className="space-y-4">
                      <label className="block">
                        <span className="hw-label">Rows</span>
                        <input 
                          type="number" 
                          value={state.config.rows} 
                          onChange={(e) => updateConfig(parseInt(e.target.value), state.config.cols)}
                          className="w-full bg-hw-bg border border-hw-border rounded p-2 text-hw-accent font-mono"
                        />
                      </label>
                      <label className="block">
                        <span className="hw-label">Columns</span>
                        <input 
                          type="number" 
                          value={state.config.cols} 
                          onChange={(e) => updateConfig(state.config.rows, parseInt(e.target.value))}
                          className="w-full bg-hw-bg border border-hw-border rounded p-2 text-hw-accent font-mono"
                        />
                      </label>
                    </div>
                    <div className="flex flex-col justify-end">
                      <div className="hw-panel p-4 bg-hw-accent/5 border-hw-accent/20">
                        <div className="hw-label">Total Samples</div>
                        <div className="text-3xl font-mono text-hw-accent">{state.config.rows * state.config.cols}</div>
                      </div>
                    </div>
                  </div>
                </motion.div>
              )}
              {activeTab === 'system' && (
                <motion.div 
                  key="system"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex-1 p-6 overflow-hidden flex flex-col"
                >
                  <div className="flex items-center justify-between mb-4">
                    <div className="hw-label">Python Logic Engine (hardware_api.py)</div>
                    <div className={cn(
                      "px-3 py-1 rounded-full text-[10px] font-bold border",
                      state.pythonBridge === 'online' ? "bg-hw-accent/10 border-hw-accent text-hw-accent" : "bg-hw-danger/10 border-hw-danger text-hw-danger"
                    )}>
                      LOGIC ENGINE {(state.pythonBridge || 'offline').toUpperCase()}
                    </div>
                  </div>
                  
                  <div className="flex-1 bg-black/50 rounded-lg border border-hw-border p-4 font-mono text-[11px] overflow-y-auto whitespace-pre text-hw-text-dim">
{`# SoilSense v4.0 Logic Engine
# This Python script handles all hardware timing, 
# gantry movement, and soil analysis logic.

def run_sequence():
    log("Starting automated soil analysis sequence...")
    state["process"]["isRunning"] = True
    
    for r in range(rows):
        for c in range(cols):
            # 1. Move Gantry
            ports["gantry"].write(f"{x},{y}\\n".encode())
            
            # 2. Scoop Down
            ports["scoop"].write(b"1\\n")
            
            # 3. Stir
            ports["stirrer"].write(b"1\\n")
            time.sleep(3)
            ports["stirrer"].write(b"0\\n")
            
            # 4. Scoop Up
            ports["scoop"].write(b"0\\n")
            
            # 5. Analyze
            soil_type = analyze_with_jetson()
            state["process"]["soilTypes"][index] = soil_type`}
                  </div>
                  
                  <div className="mt-4 p-4 bg-hw-accent/5 border border-hw-accent/20 rounded-lg">
                    <h3 className="text-hw-accent font-bold mb-2">Raspberry Pi Automatic Setup:</h3>
                    <ol className="text-[11px] space-y-1 list-decimal list-inside text-hw-text-dim">
                      <li>Run <code className="bg-black px-1 rounded">./setup.sh</code> to install all dependencies.</li>
                      <li>Run <code className="bg-black px-1 rounded">npm start</code> to launch the entire system.</li>
                      <li>The Python Logic Engine will start automatically on port 5001.</li>
                      <li>The UI Host will start on port 3000 and proxy all logic to Python.</li>
                    </ol>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>

          {/* Bottom Controls */}
          <div className="hw-panel p-4 flex gap-4">
            <button onClick={startProcess} disabled={state.process.isRunning} className={cn(BUTTON_PRIMARY, "flex-1 h-16 flex items-center justify-center gap-3 text-xl")}>
              <Play className="w-6 h-6 fill-current" /> {state.process.isRunning ? "SEQUENCE RUNNING..." : "START SEQUENCE"}
            </button>
            <button onClick={stopProcess} className={cn(BUTTON_DANGER, "flex-1 h-16 flex items-center justify-center gap-3 text-xl")}>
              <AlertTriangle className="w-6 h-6" /> EMERGENCY STOP
            </button>
            <button onClick={resetSystem} className={cn(BUTTON_SECONDARY, "h-16 px-8 flex items-center justify-center gap-2")}>
              <RotateCcw className="w-5 h-5" /> RESET
            </button>
          </div>
        </div>

        {/* Right Column: Video & Logs */}
        <div className="col-span-4 flex flex-col gap-4 overflow-hidden">
          {/* Live Feed Placeholder */}
          <div className="hw-panel aspect-video relative overflow-hidden bg-black">
            <div className="absolute top-2 left-2 flex items-center gap-2 z-10">
              <div className="w-2 h-2 bg-hw-danger rounded-full animate-pulse" />
              <span className="hw-label m-0 text-white drop-shadow-md">JETSON LIVE FEED</span>
            </div>
            <div className="w-full h-full flex flex-col items-center justify-center text-hw-text-dim">
              <Video className="w-12 h-12 mb-2 opacity-20" />
              <span className="text-[10px] font-mono uppercase tracking-widest opacity-40">Waiting for Stream...</span>
            </div>
            {/* Future Stream Implementation: <video src={streamUrl} autoPlay muted /> */}
          </div>

          {/* Logs */}
          <div className="hw-panel flex-1 p-4 flex flex-col overflow-hidden">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Terminal className="w-4 h-4 text-hw-accent" />
                <span className="hw-label m-0">System Logs</span>
              </div>
              <div className="text-[10px] font-mono text-hw-accent animate-pulse">LIVE</div>
            </div>
            <div className="flex-1 overflow-y-auto font-mono text-[10px] space-y-1 bg-black/30 p-3 rounded-lg border border-hw-border">
              {state.process.logs.map((log, i) => (
                <div key={i} className="flex gap-2">
                  <span className="text-hw-text-dim">[{new Date().toLocaleTimeString([], { hour12: false })}]</span>
                  <span className={cn(
                    log.includes('ERROR') ? 'text-hw-danger' : 
                    log.includes('SUCCESS') ? 'text-hw-accent' : 
                    log.includes('[GANTRY]') ? 'text-hw-warning' : 'text-hw-text'
                  )}>
                    {log}
                  </span>
                </div>
              ))}
              <div ref={logEndRef} />
            </div>
          </div>
        </div>
      </main>

      {/* Footer */}
      <footer className="hw-panel px-4 py-2 flex items-center justify-between text-[10px] font-mono text-hw-text-dim">
        <div className="flex gap-4">
          <span>LATENCY: 42ms</span>
          <span>JETSON: CONNECTED</span>
          <span>STORAGE: SD-CARD (128GB)</span>
        </div>
        <div>© 2026 SOILSENSE AUTOMATION SYSTEMS</div>
      </footer>
    </div>
  );
}

function StatusIndicator({ label, status }: { label: string, status: string }) {
  const isConnected = status === 'connected';
  const isError = status === 'error';
  
  return (
    <div className="flex items-center gap-2">
      <div className={cn(
        "led-indicator", 
        isConnected ? "led-on" : isError ? "led-error" : "led-off"
      )} />
      <span className="hw-label m-0">{label}</span>
    </div>
  );
}

function NavButton({ active, onClick, icon, label }: { active: boolean, onClick: () => void, icon: React.ReactNode, label: string }) {
  return (
    <button 
      onClick={onClick}
      className={cn(
        "flex flex-col items-center justify-center w-16 h-12 rounded-lg transition-all",
        active ? "bg-hw-accent text-black" : "bg-hw-border text-hw-text-dim hover:text-hw-text"
      )}
    >
      {icon}
      <span className="text-[8px] font-bold mt-1">{label}</span>
    </button>
  );
}

function DebugPanel({ title, icon, children }: { title: string, icon: React.ReactNode, children: React.ReactNode }) {
  return (
    <div className="space-y-4 p-4 border border-hw-border rounded-lg bg-hw-bg/30">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="font-bold">{title}</span>
      </div>
      {children}
    </div>
  );
}

function DebugButton({ icon, onClick }: { icon: React.ReactNode, onClick: () => void }) {
  return (
    <button 
      onClick={onClick}
      className={cn(BUTTON_SECONDARY, "w-10 h-10 p-0 flex items-center justify-center hover:bg-hw-accent hover:text-black transition-colors")}
    >
      {icon}
    </button>
  );
}
