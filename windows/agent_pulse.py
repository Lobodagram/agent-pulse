"""Windows preview: portable always-on-top widget; Tk UI, shared read-only collector."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import queue
import sys
import threading
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk, messagebox
from pulse_tray import Tray, Instance
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import collector
import analytics
import instrumentation
from journal import Journal
import providers
from platform_support import state_directory

BG='#151a1d';FG='#f2f6f4';MINT='#a4e8cd';QUIET='#a6b4b0'

class Pulse:
    def __init__(self,root,fixture=None,smoke=False,language='en'):
        self.root=root;self.state=state_directory();self.fixture=fixture;self.smoke=smoke;self.data={};self.loading=False;self.page=0;self.pending=queue.Queue();self.language=language;self.auth_revision=0;self.auth_marks={};self.reading_limits=False
        root.title('Agent Pulse');root.geometry('400x310+100+100');root.configure(bg=BG);root.overrideredirect(True);root.attributes('-topmost',True)
        header=tk.Frame(root,bg=BG);header.pack(fill='x',padx=14,pady=(8,4))
        title=tk.Label(header,text='● AGENT PULSE'+(' · DEMO' if fixture else ''),bg=BG,fg=MINT,font=('Segoe UI',10,'bold'));title.pack(side='left')
        title.bind('<Button-1>',self.begin_drag);title.bind('<B1-Motion>',self.drag)
        for text,command in [('×',self.quit),('⌄',self.collapse),('⚙',self.settings),('▥',self.analysis),('↻',self.refresh)]:
            tk.Button(header,text=text,command=command,bg=BG,fg=FG,bd=0,width=2).pack(side='right')
        self.content=tk.Frame(root,bg=BG);self.content.pack(fill='both',expand=True,padx=16)
        self.footer=tk.Frame(root,bg=BG);self.footer.pack(fill='x',padx=16,pady=6)
        tk.Button(self.footer,text='‹',command=lambda:self.change_page(-1),bg=BG,fg=MINT,bd=0).pack(side='left')
        self.page_label=tk.Label(self.footer,bg=BG,fg=QUIET);self.page_label.pack(side='left')
        tk.Button(self.footer,text='›',command=lambda:self.change_page(1),bg=BG,fg=MINT,bd=0).pack(side='left')
        self.status=tk.Label(self.footer,text='Loading…',bg=BG,fg=QUIET,font=('Segoe UI',9));self.status.pack(side='right')
        self.scale=1.0
        if not fixture:
            value=providers.load_config(self.state).get('widgetScale',1)
            self.scale=min(1,max(.8,value)) if isinstance(value,(int,float)) and not isinstance(value,bool) else 1
        grip=tk.Label(self.footer,text='◢',bg=BG,fg=QUIET,cursor='sizing');grip.pack(side='right')
        grip.bind('<Button-1>',self.begin_resize);grip.bind('<B1-Motion>',self.resize_drag);grip.bind('<ButtonRelease-1>',lambda e:self.save_scale())
        self.set_scale(self.scale,save=False)
        self.tray=None;self.display_mode='floating';self.smoke_error=None;self.tray_initialization_error=None
        try:self.tray=Tray(root,self.toggle_widget,self.tray_menu,self.tray_unavailable)
        except (OSError,AttributeError) as error:self.tray_initialization_error=str(error)
        root.protocol('WM_DELETE_WINDOW',self.quit)
        if not fixture:self.set_display_mode(providers.load_config(self.state).get('displayMode','floating'),save=False)
        self.auth_marks=self.authentication_metadata();self.refresh();root.after(5000,self.check_authentication);root.after(100,self.poll);root.after(300000,self.periodic);root.after(60000,self.limits)
    def quit(self):
        if getattr(self,'tray',None):self.tray.close()
        self.root.destroy()
    def tray_unavailable(self):
        self.root.deiconify();self.display_mode='floating'
    def set_display_mode(self,mode,save=True):
        ready=bool(self.tray and self.tray.available)
        self.display_mode='tray' if mode=='tray' and ready else 'floating'
        if self.display_mode=='tray':self.root.withdraw()
        else:self.root.deiconify()
        if save and not self.fixture:
            config=providers.load_config(self.state);config['displayMode']=self.display_mode;providers.atomic_json(self.state/'config.json',config)
        return mode!='tray' or ready
    def collapse(self):
        if not self.set_display_mode('tray'):
            messagebox.showinfo('Agent Pulse',self.t('System tray unavailable; widget remains visible.','Трей недоступен; виджет остаётся видимым.'))
    def toggle_widget(self):
        if self.root.state()=='withdrawn':
            self.root.deiconify();self.root.lift();self.root.focus_force()
        else:self.root.withdraw()
    def tray_menu(self):
        menu=tk.Menu(self.root,tearoff=False)
        for title,action in [(self.t('Show / hide widget','Показать / скрыть виджет'),self.toggle_widget),(self.t('Analytics','Аналитика'),self.analysis),(self.t('Settings','Настройки'),self.settings),(self.t('Refresh','Обновить'),self.refresh),(self.t('Quit','Выйти'),self.quit)]:menu.add_command(label=title,command=action)
        try:menu.tk_popup(self.root.winfo_pointerx(),self.root.winfo_pointery())
        finally:menu.grab_release()
    def update_tray(self):
        if not self.tray:return
        lines=['Agent Pulse']
        for p in self.data.get('providers',[])[:2]:
            quotas=p.get('quotas',[]);remaining=quotas[0].get('remainingPercent') if quotas else None;tokens=p.get('todayTokens')
            value=f'{int(remaining)}%' if remaining is not None else f'{tokens:,.0f} '+self.t('tokens today','токенов сегодня') if tokens is not None else self.t('not reported','не передано')
            lines.append(p['name']+': '+value)
        self.tray.update('\n'.join(lines))
    def begin_resize(self,e):self.resize_start=(e.x_root,self.root.winfo_width())
    def resize_drag(self,e):self.set_scale((self.resize_start[1]+e.x_root-self.resize_start[0])/400,save=False)
    def save_scale(self):
        if not self.fixture:
            config=providers.load_config(self.state);config['widgetScale']=self.scale;providers.atomic_json(self.state/'config.json',config)
    def set_scale(self,value,save=True):
        self.scale=min(1,max(.8,float(value)));self.root.geometry(f'{round(400*self.scale)}x{round(310*self.scale)}')
        def visit(w):
            if isinstance(w,tk.Toplevel):return
            if 'font' in w.keys():
                if not hasattr(w,'_pulse_font'):w._pulse_font=tkfont.Font(font=w.cget('font')).actual()
                f=w._pulse_font;w.configure(font=(f['family'],max(8,round(abs(f['size'])*self.scale)),f['weight']))
            if 'wraplength' in w.keys() and float(w.cget('wraplength'))>0:w.configure(wraplength=round(400*self.scale-32))
            for child in w.winfo_children():visit(child)
        visit(self.root)
        if save:self.save_scale()
    def t(self,en,ru):return ru if self.language=='ru' else en
    def begin_drag(self,e):self.offset=(e.x_root-self.root.winfo_x(),e.y_root-self.root.winfo_y())
    def drag(self,e):self.root.geometry(f'+{e.x_root-self.offset[0]}+{e.y_root-self.offset[1]}')
    def change_page(self,n):self.page=(self.page+n)%max(1,(len(self.data.get('providers',[]))+1)//2);self.render()
    def periodic(self):self.refresh();self.root.after(300000,self.periodic)
    def authentication_metadata(self):
        home=Path.home();paths={'codex':Path(os.environ.get('CODEX_HOME',str(home/'.codex')))/'auth.json','glm':home/'.zcode/v2/provider_config.json','claude':home/'.claude/.credentials.json','kimi':home/'.kimi/config.toml','qwen':home/'.qwen/oauth_creds.json'}
        selected={p['id'] for p in self.data.get('providers',[])} or {'codex','glm'};result={}
        for provider,path in paths.items():
            if provider not in selected:continue
            try:
                st=path.stat();result[provider]=(st.st_mtime_ns,st.st_size,st.st_ino)
            except OSError:result[provider]=None
        return result
    def check_authentication(self):
        if not self.fixture:
            marks=self.authentication_metadata()
            if marks!=self.auth_marks:
                changed={p for p in set(marks)|set(self.auth_marks) if marks.get(p)!=self.auth_marks.get(p)};self.auth_marks=marks;self.auth_revision+=1
                for p in self.data.get('providers',[]):
                    if p['id'] in changed:p.update(quotas=[],quotaObservedAt=None,accountScope=None,todayTokens=None,lifetimeTokens=None,periodTokens=None,contextTokens=None,status='unavailable',subscription={'date':None,'kind':'renewal','source':'manual'})
                self.render();self.request_limits();self.refresh()
        self.root.after(5000,self.check_authentication)
    def request_limits(self):
        if self.fixture or self.reading_limits or not any(p['id']=='codex' for p in self.data.get('providers',[])):return
        self.reading_limits=True;revision=self.auth_revision
        def collect():
            try:self.pending.put(('limits',revision,collector.collect_codex('',providers.load_config(self.state),quota_only=True,directory=self.state)[0]))
            except Exception:self.pending.put(('limits',revision,{'status':'unavailable'}))
        threading.Thread(target=collect,daemon=True).start()
    def limits(self):self.request_limits();self.root.after(60000,self.limits)
    def refresh(self):
        if self.loading:return
        self.loading=True;revision=self.auth_revision
        def collect():
            try:
                data=json.loads(Path(self.fixture).read_text(encoding='utf-8')) if self.fixture else collector.snapshot(self.state)
                self.pending.put(('ok',revision,data))
            except Exception:self.pending.put(('error',revision,None))
        threading.Thread(target=collect,daemon=True).start()
    def poll(self):
        try:
            kind,revision,data=self.pending.get_nowait()
            if kind=='limits':self.reading_limits=False
            else:self.loading=False
            if revision!=self.auth_revision:
                if kind=='limits':self.request_limits()
                else:self.refresh()
                self.root.after(100,self.poll);return
            if kind=='limits':
                if data.get('status')=='ready':
                    for p in self.data.get('providers',[]):
                        if p['id']=='codex':
                            switched=p.get('accountScope') is not None and data.get('accountScope') is not None and p['accountScope']!=data['accountScope']
                            if switched:
                                self.auth_revision+=1;p.update(todayTokens=None,lifetimeTokens=None,subscription={'date':None,'kind':'renewal','source':'manual'})
                            p.update(quotas=data['quotas'],quotaObservedAt=data.get('quotaObservedAt'),accountScope=data.get('accountScope'))
                            if switched:self.refresh()
                    self.render()
                self.root.after(100,self.poll);return
            self.loading=False
            if kind=='ok':
                old=next((p for p in self.data.get('providers',[]) if p['id']=='codex'),None)
                new=next((p for p in data.get('providers',[]) if p['id']=='codex'),None)
                if old and new and old.get('accountScope')==new.get('accountScope') and (old.get('quotaObservedAt') or 0)>(new.get('quotaObservedAt') or 0):new.update(quotas=old['quotas'],quotaObservedAt=old['quotaObservedAt'])
                self.data=data;self.status.config(text=self.t('Local counters · UTC','Локальные счётчики · UTC'));self.render()
            else:self.status.config(text=self.t('Unavailable; retained last data','Нет связи; сохранены данные'))
            if self.smoke:
                try:
                    assert not self.tray_initialization_error,self.tray_initialization_error
                    name='Local\\AgentPulseSmoke'+str(os.getpid())
                    first=Instance(name);second=Instance(name)
                    try:assert first.owns and (not second.owns or sys.platform!='win32')
                    finally:second.close();first.close()
                    third=Instance(name)
                    try:assert third.owns
                    finally:third.close()
                    self.analysis();self.root.update_idletasks();assert self.data.get('providers') and self.root.attributes('-topmost')
                    for size in (.8,.9,1):
                        self.set_scale(size,save=False);self.root.update_idletasks()
                        assert self.root.winfo_width()==round(400*size)
                        assert self.content.winfo_reqheight()<=self.content.winfo_height(), f'Widget fields clipped at {size}: requested {self.content.winfo_reqheight()}, available {self.content.winfo_height()}'
                    if self.set_display_mode('tray',save=False):
                        assert self.root.state()=='withdrawn'
                        self.tray.user.SendMessageW(self.tray.hwnd,self.tray.MESSAGE,1,0x202)
                        self.root.update();assert self.root.state()!='withdrawn'
                        self.toggle_widget();assert self.root.state()=='withdrawn'
                        self.tray.restore();assert self.tray.available
                        print('PASS: native tray registration, own click callback, collapse, restore')
                    else:
                        assert self.root.state()!='withdrawn'
                        print('PASS: tray unavailable fallback; Explorer interaction unverified')
                    self.set_display_mode('floating',save=False)
                except Exception as error:self.smoke_error=str(error)
                self.root.after(100,self.quit)
        except queue.Empty:pass
        self.root.after(100,self.poll)
    def render(self):
        for c in self.content.winfo_children():c.destroy()
        allp=self.data.get('providers',[]);pages=max(1,(len(allp)+1)//2);self.page%=pages;self.page_label.config(text=f'{self.page+1}/{pages}')
        for p in allp[self.page*2:self.page*2+2]:
            tk.Label(self.content,text=p['name']+' · '+p['status'],bg=BG,fg=QUIET,font=('Segoe UI',10,'bold'),anchor='w').pack(fill='x',pady=(3,1))
            q=p.get('quotas',[])[:2]
            if q:
                text='  '.join(('—' if x.get('remainingPercent') is None else f"{int(x['remainingPercent'])}%")+' '+(self.t('week','неделя') if (x.get('durationMinutes') or 0)>=10080 else self.t('window','окно')) for x in q)
            else:
                v=p.get('todayTokens');label=self.t('tokens today','токены сегодня')
                if v is None:v=p.get('periodTokens');label=self.t('local period tokens','локальные токены периода')
                if v is None:v=p.get('contextTokens');label=self.t('context size, not spend','контекст, не расход')
                text=('—' if v is None else f'{v:,.0f}')+' · '+label
            tk.Label(self.content,text=text,bg=BG,fg=MINT,font=('Segoe UI',14),anchor='w').pack(fill='x')
            if q:
                tokens=p.get('todayTokens');resets=[datetime.fromtimestamp(x['resetsAt']).strftime('%d %b %H:%M') for x in q if isinstance(x.get('resetsAt'),(int,float))]
                line=self.t('Today · UTC: ','Сегодня · UTC: ')+(self.t('awaiting report','жду отчёт') if tokens is None and p.get('todayTokenStatus')=='account-day-pending' else self.t('not reported','не передано') if tokens is None else f'{tokens:,.0f}'+(self.t(' · partial',' · частично') if p.get('todayTokenCoverage')=='partial-local' else ''))
                tk.Label(self.content,text=line,bg=BG,fg=QUIET,font=('Segoe UI',8),anchor='w',wraplength=365).pack(fill='x')
                tk.Label(self.content,text=self.t('Reset: ','Сброс: ')+(' / '.join(resets) or '—'),bg=BG,fg=QUIET,font=('Segoe UI',8),anchor='w',wraplength=365).pack(fill='x')
            if q:
                at=p.get('quotaObservedAt',p.get('observedAt'))
                tk.Label(self.content,text=self.t('Limit read: ','Лимит получен: ')+(datetime.fromtimestamp(at).strftime('%H:%M:%S') if at else '—'),bg=BG,fg=QUIET,font=('Segoe UI',8),anchor='w').pack(fill='x')
            s=p['subscription'];date=s.get('date');billing=self.t('Billing date not set','Дата подписки не указана') if not date else s['kind']+': '+date+' · '+self.t('manual','вручную')
            if s['kind']=='none':billing=self.t('No subscription','Без подписки')
            tk.Label(self.content,text=billing,bg=BG,fg=QUIET,font=('Segoe UI',9),anchor='w').pack(fill='x')
        self.set_scale(self.scale,save=False)
        self.update_tray()
    def window(self,title):
        w=tk.Toplevel(self.root);w.title(title);w.geometry('760x600');w.configure(bg=BG);w.attributes('-topmost',True);return w
    def analysis(self):
        w=self.window(self.t('Agent Pulse · analytics','Agent Pulse · аналитика'));book=ttk.Notebook(w);book.pack(fill='both',expand=True,padx=12,pady=12)
        def page(title):
            f=tk.Frame(book,bg=BG);book.add(f,text=title);return f
        def textview(f,lines):
            t=tk.Text(f,bg=BG,fg=FG,wrap='word',font=('Consolas',11));scroll=ttk.Scrollbar(f,command=t.yview);t.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');t.pack(expand=True,fill='both',padx=8,pady=8);t.insert('1.0','\n'.join(str(x) for x in lines));t.configure(state='disabled');return t
        overview=page(self.t('Overview','Обзор'));workflows=page(self.t('Workflows','Сценарии'));sessions=page(self.t('Sessions','Сессии'));comparison=page(self.t('Compare','Сравнение'))
        report=self.data.get('analytics',{});lines=[self.t('Tokens, quotas and billing dates are separate. Missing is unknown.','Токены, лимиты и даты оплаты различаются. Пропуск неизвестен.'),'']
        for p in self.data.get('providers',[]):
            lines += [p['name']+' · '+p['status'],self.t('Tokens today: ','Токены сегодня: ')+str(p.get('todayTokens')),p.get('tokenCoverage',''),'']
        for d in self.data.get('history',[]):lines.append(f"{d['date']}  {d['provider']:10}  {d['tokens']:>12,.0f}")
        lines+=['',self.t('OBSERVED COVERAGE','НАБЛЮДАЕМЫЙ ОХВАТ')]
        for c in report.get('coverage',[]):lines.append(f"{c['provider']}: {c['state']} · {c['pairedCalls']}/{c['calls']} · rejected {c['rejected']}")
        textview(overview,lines)
        tk.Label(workflows,text=self.t('Suggestions need review; repeated does not mean waste.','Предложения требуют проверки; повтор не доказывает лишнюю работу.'),bg=BG,fg=QUIET,wraplength=670).pack(anchor='w',padx=8,pady=8)
        finder=ttk.Treeview(workflows,columns=('provider','repeats'),show='tree headings',height=7);finder.heading('#0',text=self.t('Workflow','Сценарий'));finder.heading('provider',text=self.t('Client','Клиент'));finder.heading('repeats',text=self.t('Occurrences','Повторы'));finder.column('provider',width=90,stretch=False);finder.column('repeats',width=80,stretch=False);finder.pack(fill='x',padx=8)
        findings=report.get('findings',[])
        for i,r in enumerate(findings):finder.insert('','end',iid=str(i),text=r['titleRu'] if self.language=='ru' else r['title'],values=(r['provider'],r['occurrences']))
        info=textview(workflows,[self.t('Select a finding to inspect evidence.','Выберите наблюдение для просмотра примеров.') if findings else self.t('Not enough paired events. Enable observers in Settings.','Недостаточно пар событий. Включите наблюдатель в настройках.')])
        def finding_selected(_):
            if not finder.selection():return
            r=findings[int(finder.selection()[0])];calls=[c for c in report.get('recentCalls',[]) if c['id'] in r['evidenceIds']]
            lines=[r['suggestionRu'] if self.language=='ru' else r['suggestion'],' → '.join(r['sequence']),r['inventoryStatus'],self.t('No per-tool token estimate.','Токены каждому инструменту не приписываются.'),'']+[f"{c['tool']} · {c['template']} · {c['outcome']} · {c['durationMs']} ms" for c in calls]
            if not calls:lines.append(self.t('Use local MCP/CLI for evidence outside recent preview.','Примеры вне свежего списка доступны через локальный MCP/CLI.'))
            info.configure(state='normal');info.delete('1.0','end');info.insert('1.0','\n'.join(lines));info.configure(state='disabled')
        finder.bind('<<TreeviewSelect>>',finding_selected)
        tree=ttk.Treeview(sessions,columns=('calls','failed'),show='tree headings',height=6);tree.heading('#0',text=self.t('Session','Сессия'));tree.heading('calls',text=self.t('Calls','Вызовы'));tree.heading('failed',text=self.t('Failed','Ошибки'));tree.column('calls',width=70,stretch=False);tree.column('failed',width=70,stretch=False);tree.pack(fill='x',padx=8,pady=8)
        items=report.get('sessions',[])
        for i,r in enumerate(items):tree.insert('','end',iid=str(i),text=r['provider']+' · '+r['id'][:8],values=(r['calls'],r['failed']))
        row=tk.Frame(sessions,bg=BG);row.pack(fill='x',padx=8);label=tk.StringVar();variant=tk.StringVar(value='before');outcome=tk.StringVar(value='unknown')
        for title,var in [(self.t('Task label','Метка'),label),(self.t('Variant','Вариант'),variant)]:tk.Label(row,text=title,bg=BG,fg=FG).pack(side='left');ttk.Entry(row,textvariable=var,width=13).pack(side='left',padx=3)
        ttk.Combobox(row,textvariable=outcome,values=['unknown','accepted','failed','rework'],width=10,state='readonly').pack(side='left')
        detail=textview(sessions,[self.t('Select a session. Only sanitized metadata is shown.','Выберите сессию. Показываются только очищенные метаданные.')])
        def selected(_):
            if not tree.selection():return
            r=items[int(tree.selection()[0])];label.set(r.get('label') or '');variant.set(r.get('variant') or 'before');outcome.set(r['outcome'])
            calls=[c for c in report.get('recentCalls',[]) if c['session']==r['id']]
            if not self.fixture:
                j=Journal(self.state)
                try:calls=j.calls(r['id'])[:500]
                finally:j.close()
            lines=[self.t('Wall times may overlap; they are not summed.','Времена могут пересекаться; они не суммируются.'),'']+[f"{c['category']} · {c['tool']} · {c['outcome']}\n  {c['template']}\n  {c['durationMs']} ms · {c['durationSource']}" for c in calls]
            detail.configure(state='normal');detail.delete('1.0','end');detail.insert('1.0','\n'.join(lines));detail.configure(state='disabled')
        tree.bind('<<TreeviewSelect>>',selected)
        def annotate():
            if self.fixture or not tree.selection():return
            j=Journal(self.state)
            try:j.annotate(items[int(tree.selection()[0])]['id'],label.get(),outcome.get(),variant.get());self.refresh()
            except ValueError:messagebox.showerror('Agent Pulse',self.t('Use nonsensitive ASCII labels without spaces.','Используйте нечувствительные ASCII-метки без пробелов.'))
            finally:j.close()
        ttk.Button(row,text=self.t('Save review','Сохранить'),command=annotate).pack(side='left',padx=3)
        tk.Label(comparison,text=self.t('Label at least 3 sessions per variant. Equal difficulty/model settings need review.','Отметьте хотя бы 3 сессии на вариант. Сложность задач и настройки модели проверяете вы.'),bg=BG,fg=QUIET,wraplength=670).pack(pady=10)
        row=tk.Frame(comparison,bg=BG);row.pack(fill='x',padx=8);task=tk.StringVar();before=tk.StringVar(value='before');after=tk.StringVar(value='after')
        for var in [task,before,after]:ttk.Entry(row,textvariable=var,width=18).pack(side='left',padx=3)
        result=textview(comparison,[self.t('Observational comparison only. No promised token saving or causal claim.','Сравнение наблюдений. Без обещаний экономии токенов и утверждений о причинности.')])
        def compare():
            if self.fixture:return
            j=Journal(self.state)
            try:value=analytics.compare(j,task.get(),before.get(),after.get());result.configure(state='normal');result.delete('1.0','end');result.insert('1.0',json.dumps(value,ensure_ascii=False,indent=2));result.configure(state='disabled')
            except ValueError:messagebox.showerror('Agent Pulse',self.t('Invalid labels','Проверьте метки'))
            finally:j.close()
        ttk.Button(row,text=self.t('Compare','Сравнить'),command=compare).pack(side='left')
        if self.smoke:
            for index in range(4):book.select(index);w.update_idletasks()
            if findings:finder.selection_set('0');finding_selected(None)
            if items:tree.selection_set('0');selected(None)
    def settings(self):
        w=self.window(self.t('Agent Pulse · settings','Agent Pulse · настройки'))
        canvas=tk.Canvas(w,bg=BG,highlightthickness=0);scroll=ttk.Scrollbar(w,command=canvas.yview);canvas.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True)
        f=tk.Frame(canvas,bg=BG);canvas.create_window(10,10,window=f,anchor='nw');f.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        def label(s):tk.Label(f,text=s,bg=BG,fg=FG,anchor='w').pack(fill='x',pady=6)
        lang=tk.StringVar(value=self.language);ttk.Combobox(f,textvariable=lang,values=['en','ru'],state='readonly').pack(anchor='w')
        top=tk.BooleanVar(value=True);tk.Checkbutton(f,text=self.t('Always on top','Поверх окон'),variable=top,command=lambda:self.root.attributes('-topmost',top.get()),bg=BG,fg=FG,selectcolor=BG).pack(anchor='w')
        label(self.t('Widget size · or drag the lower-right corner','Размер виджета · можно тянуть за нижний правый угол'))
        size=tk.DoubleVar(value=self.scale)
        presets=tk.Frame(f,bg=BG);presets.pack(anchor='w')
        for value in (.8,.9,1):ttk.Button(presets,text=f'{round(value*100)}%',command=lambda v=value:(size.set(v),self.set_scale(v))).pack(side='left')
        ttk.Scale(f,from_=.8,to=1,variable=size,command=lambda v:self.set_scale(float(v),save=False)).pack(fill='x')
        label(self.t('Placement · tray icon opens the full widget','Размещение · значок в трее открывает полное табло'))
        placement=tk.StringVar(value=self.display_mode)
        ttk.Combobox(f,textvariable=placement,values=['floating','tray'],state='readonly').pack(anchor='w')
        label(self.t('Hover tray icon for counters. Windows may put it in the hidden-icons area.','Счётчики — при наведении на значок. Windows может убрать его под стрелку скрытых значков.'))
        label(self.t('Clients · see provider guide for setup','Клиенты · настройка по инструкции'));enabled={p['id'] for p in self.data.get('providers',[])};flags={}
        for spec in providers.CATALOG:
            var=tk.BooleanVar(value=spec['id'] in enabled);flags[spec['id']]=var
            tk.Checkbutton(f,text=spec['name']+' · '+spec['mode'],variable=var,bg=BG,fg=FG,selectcolor=BG).pack(anchor='w')
        patterns=tk.BooleanVar(value=self.data.get('localPatterns',False));tk.Checkbutton(f,text=self.t('Optional bounded Codex events (off by default)','Ограниченные события Codex (по умолчанию выкл.)'),variable=patterns,bg=BG,fg=FG,selectcolor=BG).pack(anchor='w')
        tokens=tk.BooleanVar(value=self.data.get('localTokens',False));tk.Checkbutton(f,text=self.t('Local Codex tokens today · partial, UTC · off by default','Локальные токены Codex сегодня · частично, UTC · по умолчанию выкл.'),variable=tokens,bg=BG,fg=FG,selectcolor=BG).pack(anchor='w')
        def apply():
            self.save_scale()
            self.language=lang.get()
            if not self.set_display_mode(placement.get()):messagebox.showinfo('Agent Pulse',self.t('Tray unavailable; floating widget retained.','Трей недоступен; виджет сохранён на экране.'))
            if not self.fixture:
                config=providers.load_config(self.state);config.update(enabledProviders=[i for i,v in flags.items() if v.get()],localPatterns=patterns.get(),localTokens=tokens.get());providers.atomic_json(self.state/'config.json',config)
            self.refresh();w.destroy()
        ttk.Button(f,text=self.t('Apply','Применить'),command=apply).pack(anchor='w',pady=10)
        label(self.t('Local observers · start a new client session after setup','Локальные наблюдатели · после настройки начните новую сессию'))
        def observer(provider,enabled):
            if self.fixture:return
            try:
                instrumentation.configure_hooks(provider,self.state,enabled)
                messagebox.showinfo('Agent Pulse',self.t('Configured. Start a new session; native hook trust review may be required.','Настроено. Начните новую сессию; клиент может запросить доверие хуку.'))
            except Exception:messagebox.showerror('Agent Pulse',self.t('Configuration failed','Настройка не удалась'))
        for provider in ['codex','glm','claude']:
            row=tk.Frame(f,bg=BG);row.pack(fill='x',pady=3);tk.Label(row,text=provider.upper(),bg=BG,fg=FG,width=12,anchor='w').pack(side='left')
            ttk.Button(row,text=self.t('Enable','Включить'),command=lambda p=provider:observer(p,True)).pack(side='left');ttk.Button(row,text=self.t('Remove','Удалить'),command=lambda p=provider:observer(p,False)).pack(side='left')
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
    a=argparse.ArgumentParser();a.add_argument('--fixture');a.add_argument('--smoke',action='store_true');a.add_argument('--language',choices=['en','ru'],default='en');args=a.parse_args()
    instance=Instance('Local\\AgentPulseFixture'+str(os.getpid())) if args.fixture else Instance()
    if not instance.owns:instance.close();return
    root=tk.Tk();app=Pulse(root,args.fixture,args.smoke,args.language)
    try:root.mainloop()
    finally:
        if app.tray:app.tray.close()
        instance.close()
    if args.smoke and app.smoke_error:raise SystemExit(app.smoke_error)
    if args.smoke and not app.data:raise SystemExit(1)
if __name__=='__main__':
    main()
