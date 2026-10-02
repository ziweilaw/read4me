import { contextBridge, ipcRenderer } from 'electron'

contextBridge.exposeInMainWorld('api', {
  openBook: (kind: 'pdf' | 'epub'): Promise<string | null> => ipcRenderer.invoke('open-book', kind),
  rpc: (method: string, params: object = {}): Promise<any> => ipcRenderer.invoke('rpc', method, params)
})
