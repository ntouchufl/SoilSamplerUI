export interface GantryState {
  x: number;
  y: number;
  status: 'connected' | 'disconnected' | 'error';
  targetX: number;
  targetY: number;
}

export interface StirrerState {
  active: boolean;
  status: 'connected' | 'disconnected' | 'error';
}

export interface ScoopState {
  position: 'up' | 'down';
  status: 'connected' | 'disconnected' | 'error';
}

export interface ProcessState {
  isRunning: boolean;
  currentRow: number;
  currentCol: number;
  soilTypes: (number | string | null)[]; // Results for each bag
  logs: string[];
}

export interface SystemConfig {
  rows: number;
  cols: number;
  dist: number;
}

export interface JetsonState {
  status: 'connected' | 'disconnected' | 'error';
  ip: string;
}

export interface SystemState {
  gantry: GantryState;
  stirrer: StirrerState;
  scoop: ScoopState;
  jetson: JetsonState;
  process: ProcessState;
  config: SystemConfig;
  pythonBridge: 'online' | 'offline';
  dummyMode: boolean;
}
