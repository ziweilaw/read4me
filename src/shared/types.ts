export interface Section { title: string; level: number; start: number; end: number; number: number | null }
export interface DocInfo { kind: 'pdf' | 'epub'; seg_titles: string[]; n_pages: number; page_offset: number; scanned_pages: number[]; sections: Section[] }
export interface Unit { page: number; kind: 'heading' | 'sentence'; text: string; paragraph: number }
export interface Voice { id: string; name: string; lang: string; quality: string }
export interface Command { kind: string; start: number | null; end: number | null; section: Section | null; message: string }
declare global { interface Window { api: { openBook(kind: 'pdf' | 'epub'): Promise<string | null>; rpc(m: string, p?: object): Promise<any> } } }
