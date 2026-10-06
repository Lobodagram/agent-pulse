"""Windows preview: portable always-on-top widget; Tk UI, shared read-only collector."""
import argparse
import json
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import collector
import providers
from platform_support import state_directory

BG='#151a1d';FG='#f2f6f4';MINT='#a4e8cd';QUIET='#a6b4b0'

class Pulse:
    def __init__(self,root,fixture=None,smoke=False):
        self.root=root;self.state=state_directory();self.fixture=fixture;self.smoke=smoke;self.data={};self.loading=False;self.page=0;self.pending=queue.Queue();self.language='en'
        root.title('Agent Pulse');root.geometry('370x255+100+100');root.configure(bg=BG);root.overrideredirect(True);root.attributes('-topmost',True)
        header=tk.Frame(root,bg=BG);header.pack(fill='x',padx=14,pady=(12,6))
        title=tk.Label(header,text='● AGENT PULSE'+(' · DEMO' if fixture else ''),bg=BG,fg=MINT,font=('Segoe UI',10,'bold'));title.pack(side='left')
        title.bind('<Button-1>',self.begin_drag);title.bind('<B1-Motion>',self.drag)
        for text,command in [('×',root.destroy),('⚙',self.settings),('▥',self.analysis),('↻',self.refresh)]:
            tk.Button(header,text=text,command=command,bg=BG,fg=FG,bd=0,width=3).pack(side='right')
        self.content=tk.Frame(root,bg=BG);self.content.pack(fill='both',expand=True,padx=16)
        self.footer=tk.Frame(root,bg=BG);self.footer.pack(fill='x',padx=16,pady=8)
        tk.Button(self.footer,text='‹',command=lambda:self.change_page(-1),bg=BG,fg=MINT,bd=0).pack(side='left')
        self.page_label=tk.Label(self.footer,bg=BG,fg=QUIET);self.page_label.pack(side='left')
        tk.Button(self.footer,text='›',command=lambda:self.change_page(1),bg=BG,fg=MINT,bd=0).pack(side='left')
        self.status=tk.Label(self.footer,text='Loading…',bg=BG,fg=QUIET,font=('Segoe UI',9));self.status.pack(side='right')
        self.refresh();root.after(100,self.poll);root.after(300000,self.periodic)
    def t(self,en,ru):return ru if self.language=='ru' else en
    def begin_drag(self,e):self.offset=(e.x_root-self.root.winfo_x(),e.y_root-self.root.winfo_y())
    def drag(self,e):self.root.geometry(f'+{e.x_root-self.offset[0]}+{e.y_root-self.offset[1]}')
    def change_page(self,n):self.page=(self.page+n)%max(1,(len(self.data.get('providers',[]))+1)//2);self.render()
    def periodic(self):self.refresh();self.root.after(300000,self.periodic)
    def refresh(self):
        if self.loading:return
        self.loading=True
        def collect():
            try:
                data=json.loads(Path(self.fixture).read_text(encoding='utf-8')) if self.fixture else collector.snapshot(self.state)
                self.pending.put(('ok',data))
            except Exception:self.pending.put(('error',None))
        threading.Thread(target=collect,daemon=True).start()
    def poll(self):
        try:
            kind,data=self.pending.get_nowait();self.loading=False
            if kind=='ok':self.data=data;self.status.config(text=self.t('Local counters · UTC','Локальные счётчики · UTC'));self.render()
            else:self.status.config(text=self.t('Unavailable; retained last data','Нет связи; сохранены данные'))
            if self.smoke:
                self.root.update_idletasks();assert self.data.get('providers') and self.root.attributes('-topmost');self.root.after(100,self.root.destroy)
        except queue.Empty:pass
        self.root.after(100,self.poll)
    def render(self):
        for c in self.content.winfo_children():c.destroy()
        allp=self.data.get('providers',[]);pages=max(1,(len(allp)+1)//2);self.page%=pages;self.page_label.config(text=f'{self.page+1}/{pages}')
        for p in allp[self.page*2:self.page*2+2]:
            tk.Label(self.content,text=p['name']+' · '+p['status'],bg=BG,fg=QUIET,font=('Segoe UI',10,'bold'),anchor='w').pack(fill='x',pady=(8,2))
            q=p.get('quotas',[])[:2]
            if q:
                text='  '.join(('—' if x.get('remainingPercent') is None else f"{x['remainingPercent']:.0f}%")+' '+(self.t('week','неделя') if (x.get('durationMinutes') or 0)>=10080 else self.t('window','окно')) for x in q)
            else:
                v=p.get('todayTokens');label=self.t('tokens today','токены сегодня')
                if v is None:v=p.get('periodTokens');label=self.t('local period tokens','локальные токены периода')
                if v is None:v=p.get('contextTokens');label=self.t('context size, not spend','контекст, не расход')
                text=('—' if v is None else f'{v:,.0f}')+' · '+label
            tk.Label(self.content,text=text,bg=BG,fg=MINT,font=('Segoe UI',14),anchor='w').pack(fill='x')
            s=p['subscription'];date=s.get('date');billing=self.t('Billing date not set','Дата подписки не указана') if not date else s['kind']+': '+date+' · '+self.t('manual','вручную')
            if s['kind']=='none':billing=self.t('No subscription','Без подписки')
            tk.Label(self.content,text=billing,bg=BG,fg=QUIET,font=('Segoe UI',9),anchor='w').pack(fill='x')
    def window(self,title):
        w=tk.Toplevel(self.root);w.title(title);w.geometry('760x600');w.configure(bg=BG);w.attributes('-topmost',True);return w
    def analysis(self):
        w=self.window(self.t('Agent Pulse · analytics','Agent Pulse · аналитика'))
        text=tk.Text(w,bg=BG,fg=FG,wrap='word',font=('Consolas',11));scroll=ttk.Scrollbar(w,command=text.yview);text.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');text.pack(expand=True,fill='both',padx=16,pady=16)
        lines=[self.t('Counters, quotas and billing dates are distinct. Missing is not zero.','Токены, лимиты и даты оплаты различаются. Пропуск не равен нулю.'),'']
        for p in self.data.get('providers',[]):
            lines += [p['name']+' · '+p['status'],self.t('Tokens today: ','Токены сегодня: ')+str(p.get('todayTokens')),self.t('Context gauge: ','Размер контекста: ')+str(p.get('contextTokens')),p.get('tokenSource',''),p.get('tokenCoverage','')]
            for q in p.get('quotas',[]):lines.append(f"Remaining: {q.get('remainingPercent')}% · reset epoch: {q.get('resetsAt')}")
            lines.append('')
        lines+=[self.t('DAILY TOKENS · UTC','ТОКЕНЫ ПО ДНЯМ · UTC')]
        for d in self.data.get('history',[]):lines.append(f"{d['date']}  {d['provider']:10}  {d['tokens']:>12,.0f}")
        lines+=['',self.t('REPEATED CALLS · counts, not per-tool tokens','ПОВТОРЫ · число вызовов, не токены инструментов')]
        for r in self.data.get('patterns',[]):lines.append(f"{r['provider']:10} {r['name']:40} {r['count']}\n  {r['source']}")
        lines+=['',self.t('No prompts, results, credentials or code stored in telemetry.','В телеметрии нет промптов, результатов, секретов или кода.')]
        text.insert('1.0','\n'.join(lines));text.configure(state='disabled')
    def settings(self):
        w=self.window(self.t('Agent Pulse · settings','Agent Pulse · настройки'))
        canvas=tk.Canvas(w,bg=BG,highlightthickness=0);scroll=ttk.Scrollbar(w,command=canvas.yview);canvas.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True)
        f=tk.Frame(canvas,bg=BG);canvas.create_window(10,10,window=f,anchor='nw');f.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        def label(s):tk.Label(f,text=s,bg=BG,fg=FG,anchor='w').pack(fill='x',pady=6)
        lang=tk.StringVar(value=self.language);ttk.Combobox(f,textvariable=lang,values=['en','ru'],state='readonly').pack(anchor='w')
        top=tk.BooleanVar(value=True);tk.Checkbutton(f,text=self.t('Always on top','Поверх окон'),variable=top,command=lambda:self.root.attributes('-topmost',top.get()),bg=BG,fg=FG,selectcolor=BG).pack(anchor='w')
        label(self.t('Clients · see provider guide for setup','Клиенты · настройка по инструкции'));enabled={p['id'] for p in self.data.get('providers',[])};flags={}
        for spec in providers.CATALOG:
            var=tk.BooleanVar(value=spec['id'] in enabled);flags[spec['id']]=var
            tk.Checkbutton(f,text=spec['name']+' · '+spec['mode'],variable=var,bg=BG,fg=FG,selectcolor=BG).pack(anchor='w')
        patterns=tk.BooleanVar(value=self.data.get('localPatterns',False));tk.Checkbutton(f,text=self.t('Optional bounded Codex events (off by default)','Ограниченные события Codex (по умолчанию выкл.)'),variable=patterns,bg=BG,fg=FG,selectcolor=BG).pack(anchor='w')
        def apply():
            self.language=lang.get()
            if not self.fixture:
                config=providers.load_config(self.state);config.update(enabledProviders=[i for i,v in flags.items() if v.get()],localPatterns=patterns.get());providers.atomic_json(self.state/'config.json',config)
            self.refresh();w.destroy()
        ttk.Button(f,text=self.t('Apply','Применить'),command=apply).pack(anchor='w',pady=10)
        label(self.t('Billing dates are manual: YYYY-MM-DD','Даты подписки вручную: ГГГГ-ММ-ДД'))
        for p in self.data.get('providers',[]):
            row=tk.Frame(f,bg=BG);row.pack(fill='x',pady=5);tk.Label(row,text=p['name'],width=16,bg=BG,fg=FG,anchor='w').pack(side='left')
            date=tk.StringVar(value=p['subscription'].get('date') or '');kind=tk.StringVar(value=p['subscription']['kind']);ttk.Combobox(row,textvariable=kind,values=['renewal','expiry','none'],width=9,state='readonly').pack(side='left');ttk.Entry(row,textvariable=date,width=14).pack(side='left',padx=5)
            def save(pid=p['id'],d=date,k=kind):
                if self.fixture:return
                try:
                    s=collector.Store(self.state)
                    try:s.set_subscription(pid,d.get(),k.get())
                    finally:s.db.close()
                    self.refresh()
                except ValueError:messagebox.showerror('Agent Pulse',self.t('Use a valid YYYY-MM-DD date','Введите существующую дату ГГГГ-ММ-ДД'))
            ttk.Button(row,text=self.t('Save','Сохранить'),command=save).pack(side='left')

def main():
    a=argparse.ArgumentParser();a.add_argument('--fixture');a.add_argument('--smoke',action='store_true');args=a.parse_args()
    root=tk.Tk();app=Pulse(root,args.fixture,args.smoke);root.mainloop()
    if args.smoke and not app.data:raise SystemExit(1)
if __name__=='__main__':main()
