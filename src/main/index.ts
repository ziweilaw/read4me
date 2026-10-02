import { app, BrowserWindow, dialog, ipcMain, nativeImage } from 'electron'
import { spawn, ChildProcessWithoutNullStreams } from 'node:child_process'
import { createInterface } from 'node:readline'
import { join } from 'node:path'

const root = join(__dirname, '../..')
let sidecar: ChildProcessWithoutNullStreams
let nextId = 1
const pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>()

function startSidecar() {
  if (app.isPackaged) {
    // bundled sidecar + models live in the app's Resources folder
    const exe = process.platform === 'win32' ? 'read4me-sidecar.exe' : 'read4me-sidecar'
    sidecar = spawn(join(process.resourcesPath, 'sidecar', exe), [], {
      env: { ...process.env, READ4ME_MODELS_DIR: join(process.resourcesPath, 'models') }
    })
  } else {
    const py = process.platform === 'win32' ? 'sidecar/.venv/Scripts/python.exe' : 'sidecar/.venv/bin/python'
    sidecar = spawn(join(root, py), ['server.py'], { cwd: join(root, 'sidecar') })
  }
  createInterface({ input: sidecar.stdout }).on('line', (line) => {
    const msg = JSON.parse(line)
    const p = pending.get(msg.id)
    if (!p) return
    pending.delete(msg.id)
    msg.error ? p.reject(new Error(msg.error)) : p.resolve(msg.result)
  })
  sidecar.stderr.on('data', (d) => console.error('[sidecar]', d.toString()))
}

function rpc(method: string, params: object = {}): Promise<unknown> {
  const id = nextId++
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject })
    sidecar.stdin.write(JSON.stringify({ id, method, params }) + '\n')
  })
}

app.whenReady().then(() => {
  startSidecar()
  ipcMain.handle('rpc', (_e, method: string, params: object) => rpc(method, params))
  ipcMain.handle('open-book', async (_e, kind: 'pdf' | 'epub') => {
    const r = await dialog.showOpenDialog({
      properties: ['openFile'],
      filters: [kind === 'epub' ? { name: 'EPUB book', extensions: ['epub'] } : { name: 'PDF', extensions: ['pdf'] }]
    })
    return r.canceled ? null : r.filePaths[0]
  })
  const icon = nativeImage.createFromPath(join(root, 'resources/icon.png'))
  if (process.platform === 'darwin' && !icon.isEmpty()) app.dock?.setIcon(icon)
  const win = new BrowserWindow({
    width: 1100, height: 780, title: 'Read4me', icon,
    webPreferences: { preload: join(__dirname, '../preload/index.js'), sandbox: false }
  })
  if (process.env.ELECTRON_RENDERER_URL) win.loadURL(process.env.ELECTRON_RENDERER_URL)
  else win.loadFile(join(__dirname, '../renderer/index.html'))
})

app.on('window-all-closed', () => { sidecar?.kill(); app.quit() })
