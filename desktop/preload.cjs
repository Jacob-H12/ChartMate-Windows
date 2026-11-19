'use strict';
const {contextBridge, ipcRenderer} = require('electron');
contextBridge.exposeInMainWorld('chartmateSetup', {
  start: () => ipcRenderer.invoke('setup:start'),
  retry: () => ipcRenderer.invoke('setup:retry'),
  folder: () => ipcRenderer.invoke('setup:folder'),
  onStatus: callback => {
    const listener = (_event, status) => callback(status);
    ipcRenderer.on('setup:status', listener);
    return () => ipcRenderer.removeListener('setup:status', listener);
  }
});
