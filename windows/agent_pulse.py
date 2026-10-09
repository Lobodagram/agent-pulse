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
from tkinter import ttk, messagebox, filedialog
from pulse_tray import Tray, Instance
from pulse_brand import asset
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from compact_summary import provider_line,quota_pages,tray_tooltip,window_label
import collector
from pulse_version import __version__
import analytics
import instrumentation
from journal import Journal, PROVIDERS
import providers
from agent_control import update_settings
from platform_support import state_directory,windows_launch_at_login

BG='#151a1d';FG='#f2f6f4';MINT='#a4e8cd';QUIET='#a6b4b0'

class Pulse:
    def __init__(self,root,fixture=None,smoke=False,language='en'):
        self.root=root;self.state=state_directory();self.fixture=fixture;self.smoke=smoke;self.data={};self.loading=False;self.page=0;self.pending=queue.Queue();self.language=language;self.auth_revision=0;self.auth_marks={};self.reading_limits=False
        self.utility_windows={};self.utility_press=None
        self.collapsed=False;self.compact_page=0;self.full_position=(100,100);self.refresh_failed=False
        root.title('Agent Pulse');root.geometry('400x310+100+100');root.configure(bg=BG);root.overrideredirect(True);root.attributes('-topmost',True)
        self.brand_image=tk.PhotoImage(file=str(asset('logo-32.png')))
        self.header_image=self.brand_image.subsample(2,2)
        root.iconphoto(True,self.brand_image)
        header=tk.Frame(root,bg=BG);header.pack(fill='x',padx=14,pady=(8,4))
        self.header=header;self.header_buttons=[]
        title=tk.Label(header,text='AGENT PULSE'+(' · DEMO' if fixture else ''),image=self.header_image,compound='left',padx=3,bg=BG,fg=MINT,font=('Segoe UI',10,'bold'));title.pack(side='left')
        self.header_title=title
        title.bind('<Button-1>',self.begin_drag);title.bind('<B1-Motion>',self.drag)
        for text,command in [('×',self.quit),('⌄',self.collapse),('⚙',self.settings),('▥',self.analysis),('↻',self.refresh)]:
            button=tk.Button(header,text=text,command=command,bg=BG,fg=FG,bd=0,width=2);button.pack(side='right');self.header_buttons.append(button)
            if text=='⌄':self.collapse_button=button
            if text in ('⚙','▥'):button.bind('<ButtonPress-1>',self.capture_utility_focus)
        self.content=tk.Frame(root,bg=BG);self.content.pack(fill='both',expand=True,padx=16)
        self.footer=tk.Frame(root,bg=BG);self.footer.pack(fill='x',padx=16,pady=6)
        tk.Button(self.footer,text='‹',command=lambda:self.change_page(-1),bg=BG,fg=MINT,bd=0).pack(side='left')
        self.page_label=tk.Label(self.footer,bg=BG,fg=QUIET);self.page_label.pack(side='left')
        tk.Button(self.footer,text='›',command=lambda:self.change_page(1),bg=BG,fg=MINT,bd=0).pack(side='left')
        self.status=tk.Label(self.footer,text='Loading…',bg=BG,fg=QUIET,font=('Segoe UI',9));self.status.pack(side='right')
        self.metric_mode='limits' if fixture else ('today' if providers.load_config(self.state).get('metricMode')=='today' else 'limits')
        self.metric_button=tk.Button(self.footer,text='',command=self.toggle_metric,bg=BG,fg=MINT,bd=0);self.metric_button.pack(side='left')
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
        self.auth_marks=self.authentication_metadata();self.refresh();root.after(5000,self.check_authentication);root.after(100,self.poll);root.after(300000,self.periodic);root.after(60000,self.limits);root.after(8000,self.rotate_compact)
    def toggle_metric(self):
        self.metric_mode='today' if self.metric_mode=='limits' else 'limits'
        if not self.fixture:
            update_settings(self.state,{'metricMode':self.metric_mode})
        self.render()
    def quit(self):
        if getattr(self,'tray',None):self.tray.close()
        self.root.destroy()
    def tray_unavailable(self):
        self.root.deiconify();self.display_mode='floating'
    def set_display_mode(self,mode,save=True):
        ready=bool(self.tray and self.tray.available)
        self.display_mode=mode if mode in ('floating','compact') or mode=='tray' and ready else 'floating'
        if not self.collapsed:self.full_position=(self.root.winfo_x(),self.root.winfo_y())
        self.collapsed=self.display_mode=='compact'
        self.render()
        if self.display_mode=='tray':self.root.withdraw()
        else:self.root.deiconify()
        if self.collapsed:self.position_compact()
        if save and not self.fixture:
            update_settings(self.state,{'displayMode':self.display_mode})
        return mode!='tray' or ready
    def position_compact(self):
        area=self.tray.work_area() if self.tray else None
        left,top,right,bottom=area or (0,0,self.root.winfo_screenwidth(),self.root.winfo_screenheight()-48)
        self.root.update_idletasks();self.root.geometry(f'+{max(left,right-self.root.winfo_width()-16)}+{max(top,bottom-self.root.winfo_height()-12)}')
    def collapse(self):
        if self.collapsed:self.show_full()
        else:self.set_display_mode('compact')
    def show_full(self):
        self.collapsed=False;self.root.deiconify();self.render()
        x,y=self.full_position;self.root.geometry(f'+{x}+{y}');self.root.lift();self.root.focus_force()
    def toggle_widget(self):
        if self.collapsed or self.root.state()=='withdrawn':self.show_full()
        elif self.display_mode=='tray':self.root.withdraw()
        else:self.collapse()
    def rotate_compact(self):
        if self.collapsed:
            self.compact_page+=1;self.render()
        self.root.after(8000,self.rotate_compact)
    def tray_menu(self):
        menu=tk.Menu(self.root,tearoff=False)
        for title,action in [(self.t('Show / hide widget','Показать / скрыть виджет'),self.toggle_widget),(self.t('Analytics','Аналитика'),self.analysis),(self.t('Settings','Настройки'),self.settings),(self.t('Refresh','Обновить'),self.refresh),(self.t('Quit','Выйти'),self.quit)]:menu.add_command(label=title,command=action)
        try:menu.tk_popup(self.root.winfo_pointerx(),self.root.winfo_pointery())
        finally:menu.grab_release()
    def update_tray(self):
        if self.tray:self.tray.update(tray_tooltip(self.data.get('providers',[]),self.language=='ru'))
    def begin_resize(self,e):self.resize_start=(e.x_root,self.root.winfo_width())
    def resize_drag(self,e):self.set_scale((self.resize_start[1]+e.x_root-self.resize_start[0])/400,save=False)
    def save_scale(self):
        if not self.fixture:
            update_settings(self.state,{'widgetScale':self.scale})
    def set_scale(self,value,save=True):
        self.scale=min(1,max(.8,float(value)))
        if self.collapsed:return
        self.root.geometry(f'{round(400*self.scale)}x{round(310*self.scale)}')
        def visit(w):
            if isinstance(w,tk.Toplevel):return
            if isinstance(w,tk.Label) and w.master is self.content:w.configure(bd=0,padx=0,pady=0)
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
        home=Path.home();paths={'codex':Path(os.environ.get('CODEX_HOME',str(home/'.codex')))/'auth.json','glm':home/'.zcode/v2/provider_config.json','claude':home/'.claude/.credentials.json','kimi':Path(os.environ.get('KIMI_CODE_HOME',str(home/'.kimi-code')))/'config.toml','qwen':home/'.qwen/oauth_creds.json'}
        selected={p['id'] for p in self.data.get('providers',[])} or {'codex','glm'};result={}
        for provider,path in paths.items():
            if provider not in selected:continue
            try:
                st=path.stat();result[provider]=(st.st_mtime_ns,st.st_size,st.st_ino)
            except OSError:result[provider]=None
        return result
    def save_topmost(self,value):
        self.root.attributes('-topmost',value)
        if not self.fixture:
            update_settings(self.state,{'topmost':bool(value)})
    def sync_preferences(self):
        if self.fixture:return
        config=providers.load_config(self.state)
        signature=json.dumps({k:config.get(k) for k in ('language','widgetScale','metricMode','displayMode','topmost')},sort_keys=True)
        if signature==getattr(self,'preference_signature',None):return
        self.preference_signature=signature
        self.language=config.get('language',self.language)
        self.metric_mode=config.get('metricMode',self.metric_mode)
        self.root.attributes('-topmost',config.get('topmost',True))
        scale=config.get('widgetScale',self.scale)
        if type(scale) in (float,int) and .8<=scale<=1:self.set_scale(scale,save=False)
        mode=config.get('displayMode',self.display_mode)
        if mode=='menu':mode='tray'
        if mode in ('floating','compact','tray') and mode!=self.display_mode:self.set_display_mode(mode,save=False)
        self.render()
    def check_authentication(self):
        self.sync_preferences()
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
                self.refresh_failed=False;self.data=data;self.status.config(text=self.t('Local counters · UTC','Локальные счётчики · UTC'));self.render()
            else:
                self.refresh_failed=True;self.status.config(text=self.t('Unavailable; retained last data','Нет связи; сохранены данные'));self.render()
            if self.smoke:
                try:
                    assert not self.tray_initialization_error,self.tray_initialization_error
                    if sys.platform=='win32':assert self.tray.owned_icon, 'Approved tray icon must load in source and packaged modes'
                    name='Local\\AgentPulseSmoke'+str(os.getpid())
                    first=Instance(name);second=Instance(name)
                    try:assert first.owns and (not second.owns or sys.platform!='win32')
                    finally:second.close();first.close()
                    third=Instance(name)
                    try:assert third.owns
                    finally:third.close()
                    self.analysis();self.root.update();assert self.data.get('providers') and self.root.attributes('-topmost')
                    for kind,action in [('analysis',self.analysis),('settings',self.settings)]:
                        action() if kind=='settings' else None
                        self.root.update();window=self.utility_windows[kind]
                        assert not window.attributes('-topmost')
                        window.focus_force();self.root.update();self.capture_utility_focus(None)
                        action();self.root.update();assert window.state()=='withdrawn'
                        action();self.root.update();assert self.utility_windows[kind] is window and window.state()=='normal'
                        window.iconify();self.root.update();action();self.root.update();assert window.state()=='normal'
                        window.destroy();self.root.update();action();self.root.update();assert self.utility_windows[kind] is not window
                    print('PASS: single-instance normal utility windows, active hide, hidden/minimized/closed restore')
                    self.toggle_metric();assert self.metric_mode=='today';self.toggle_metric();assert self.metric_mode=='limits'
                    for metric in ('limits','today'):
                        self.metric_mode=metric;self.render()
                        for size in (.8,.9,1):
                            self.set_scale(size,save=False);self.root.update_idletasks()
                            assert self.root.winfo_width()==round(400*size)
                            assert self.content.winfo_reqheight()<=self.content.winfo_height(), f'Widget fields clipped in {metric} at {size}: requested {self.content.winfo_reqheight()}, available {self.content.winfo_height()}'
                    self.metric_mode='limits';self.render()
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
                    self.set_display_mode('compact',save=False);self.root.update_idletasks()
                    assert self.collapsed and self.root.state()!='withdrawn'
                    assert self.content.winfo_reqheight()<=self.content.winfo_height(), 'Compact rows clipped'
                    assert self.root.winfo_height()<180
                    saved=self.data
                    try:
                        self.data=dict(saved,providers=[dict(saved['providers'][0],id='demo'+str(i),name='Demo '+str(i)) for i in range(13)])
                        seen=[]
                        for page in range(5):
                            self.compact_page=page;self.render();self.root.update_idletasks()
                            seen+=quota_pages(self.data['providers'],self.language=='ru')[page]
                            assert self.content.winfo_reqheight()<=self.content.winfo_height()
                        assert len(seen)==13
                    finally:self.data=saved;self.compact_page=0;self.render()
                    self.toggle_widget();self.root.update_idletasks();assert not self.collapsed and self.root.state()!='withdrawn'
                    self.set_display_mode('floating',save=False)
                    print('PASS: compact quota strip, all-client pages, click restore')
                except Exception as error:self.smoke_error=str(error)
                self.root.after(100,self.quit)
        except queue.Empty:pass
        self.root.after(100,self.poll)
    def render_compact(self):
        pages=quota_pages(self.data.get('providers',[]),self.language=='ru')
        index=self.compact_page%len(pages);lines=pages[index]
        self.header_title.config(text=self.t('● AP · LEFT','● AP · ОСТАЛОСЬ')+(f' {index+1}/{len(pages)}' if len(pages)>1 else '')+(' · DEMO' if self.fixture else ''))
        for button in self.header_buttons:button.pack_forget()
        self.header_buttons[0].pack(side='right');self.collapse_button.pack(side='right');self.collapse_button.config(text='↗')
        self.footer.pack_forget()
        for text in lines or [self.t('Awaiting metrics','Ожидаю показатели')]:
            label=tk.Label(self.content,text=('~' if self.refresh_failed else '')+text,bg=BG,fg=MINT,font=('Segoe UI',10),anchor='w',bd=0,padx=0,pady=0)
            label.pack(fill='x',pady=2);label.bind('<Button-1>',lambda e:self.show_full())
        self.root.update_idletasks()
        font=tkfont.Font(family='Segoe UI',size=10)
        width=min(600,max(320,max((font.measure(t)+40 for t in lines),default=320)))
        height=self.header.winfo_reqheight()+self.content.winfo_reqheight()+12
        self.root.geometry(f'{width}x{height}');self.update_tray()
    def render(self):
        self.metric_button.configure(text=self.t('Limits ⇄','Лимиты ⇄') if self.metric_mode=='limits' else self.t('Today ⇄','Сегодня ⇄'))
        for c in self.content.winfo_children():c.destroy()
        if self.collapsed:
            self.render_compact();return
        self.header_title.config(text='AGENT PULSE'+(' · DEMO' if self.fixture else ''))
        for button in self.header_buttons:button.pack(side='right')
        self.collapse_button.config(text='⌄');self.footer.pack(fill='x',padx=16,pady=6)
        allp=self.data.get('providers',[]);pages=max(1,(len(allp)+1)//2);self.page%=pages;self.page_label.config(text=f'{self.page+1}/{pages}')
        for p in allp[self.page*2:self.page*2+2]:
            tk.Label(self.content,text=p['name']+' · '+p['status'],bg=BG,fg=QUIET,font=('Segoe UI',10,'bold'),anchor='w').pack(fill='x',pady=(3,1))
            q=p.get('quotas',[])[:2]
            if q and self.metric_mode=='limits':
                text='  '.join(('—' if x.get('remainingPercent') is None else f"{int(x['remainingPercent'])}%")+' '+window_label(x.get('durationMinutes'),self.language=='ru') for x in q)
            else:
                v=p.get('todayTokens') if self.metric_mode=='today' else None
                label=self.t('tokens today · UTC','токены сегодня · UTC') if self.metric_mode=='today' else self.t('limits not reported','лимиты не переданы')
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
        w=tk.Toplevel(self.root);w.title(title);w.geometry('760x600');w.configure(bg=BG);w.attributes('-topmost',False)
        tk.Label(w,text=title,image=self.brand_image,compound='left',padx=8,bg=BG,fg=FG,font=('Segoe UI',14,'bold')).pack(anchor='w',padx=12,pady=(12,0))
        w.after_idle(w.focus_force);return w
    def capture_utility_focus(self,event):
        focused=self.root.focus_displayof()
        self.utility_press=(focused.winfo_toplevel() if focused else None,)
    def existing_utility(self,kind):
        press=self.utility_press;self.utility_press=None
        window=self.utility_windows.get(kind)
        if not window or not window.winfo_exists():return False
        focused=self.root.focus_displayof()
        active=press[0] if press is not None else (focused.winfo_toplevel() if focused else None)
        if window.state()=='normal' and active is window:window.withdraw()
        else:window.deiconify();window.lift();window.focus_force()
        return True
    def analysis(self):
        if self.existing_utility('analysis'):
            w=self.utility_windows['analysis']
            if w.state()=='normal' and self.analysis_data is not self.data:
                book=next((c for c in w.winfo_children() if isinstance(c,ttk.Notebook)),None)
                selected=book.index(book.select()) if book else 0
                for child in w.winfo_children():child.destroy()
                self.populate_analysis(w,selected)
            return
        w=self.window(self.t('Agent Pulse · analytics','Agent Pulse · аналитика'));self.utility_windows['analysis']=w
        self.populate_analysis(w)
    def populate_analysis(self,w,selected_tab=0):
        self.analysis_data=self.data
        book=ttk.Notebook(w);book.pack(fill='both',expand=True,padx=12,pady=12)
        def page(title):
            f=tk.Frame(book,bg=BG);book.add(f,text=title);return f
        def textview(f,lines):
            t=tk.Text(f,bg=BG,fg=FG,wrap='word',font=('Consolas',11));scroll=ttk.Scrollbar(f,command=t.yview);t.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');t.pack(expand=True,fill='both',padx=8,pady=8);t.insert('1.0','\n'.join(str(x) for x in lines));t.configure(state='disabled');return t
        overview=page(self.t('Overview','Обзор'));workflows=page(self.t('Workflows','Сценарии'));sessions=page(self.t('Sessions','Сессии'));comparison=page(self.t('Compare','Сравнение'))
        capabilities=page(self.t('Capabilities','Навыки'))
        daily=page(self.t('Daily tokens','Токены по дням'))
        tk.Label(daily,text=self.t('UTC daily counters · select a day for exact values. Missing is not zero.','Дневные счётчики UTC · выберите день для точных значений. Пропуск — не ноль.'),bg=BG,fg=QUIET,wraplength=560).pack(anchor='w',padx=8,pady=8)
        history=self.data.get('history',[]);days=sorted({r['date'] for r in history})
        daytree=ttk.Treeview(daily,columns=('tokens',),show='tree headings',height=6)
        daytree.heading('#0',text=self.t('Day · UTC','День · UTC'));daytree.heading('tokens',text=self.t('Reported total','Передано всего'))
        daytree.pack(fill='x',padx=8)
        for day in days:daytree.insert('','end',iid=day,text=day,values=(f"{sum(r['tokens'] for r in history if r['date']==day):,.0f}",))
        daydetail=textview(daily,[])
        def day_selected(_=None):
            if not daytree.selection():return
            day=daytree.selection()[0];detail=[day+' · UTC','']
            for p in self.data.get('providers',[]):
                r=next((r for r in history if r['date']==day and r['provider']==p['id']),None)
                detail.append(p['id'].upper()+' · '+(f"{r['tokens']:,.0f}" if r is not None else self.t('No daily counter; not zero','Дневной счётчик отсутствует; это не ноль')))
                if r is not None:detail.append(self.t('Partial local events','Частичные локальные события') if r.get('coverage')=='partial-local' else self.t('Reported daily counter · source scope varies','Переданный дневной счётчик · охват источников различается'))
            detail+=['',self.t('These daily sources do not report hourly tokens. Quota percentages are separate.','Эти дневные источники не передают почасовые токены. Проценты лимитов учитываются отдельно.')]
            daydetail.configure(state='normal');daydetail.delete('1.0','end');daydetail.insert('1.0','\n'.join(detail));daydetail.configure(state='disabled')
        daytree.bind('<<TreeviewSelect>>',day_selected)
        if days:daytree.selection_set(days[-1]);day_selected()
        report=self.data.get('analytics',{});lines=[self.t('Tokens, quotas and billing dates are separate. Missing is unknown.','Токены, лимиты и даты оплаты различаются. Пропуск неизвестен.'),'']
        for p in self.data.get('providers',[]):
            lines += [p['name']+' · '+p['status'],self.t('Tokens today: ','Токены сегодня: ')+(str(p['todayTokens']) if p.get('todayTokens') is not None else '—'),p.get('tokenCoverage',''),'']
            profile=p.get('localTokenProfile')
            if profile:
                count=lambda key:'—' if profile.get(key) is None else f"{profile[key]:,.0f}"
                rate=lambda key:'—' if profile.get(key) is None else f"{profile[key]*100:.1f}%"
                lines += [self.t('Local device · UTC ','На этом устройстве · UTC ')+profile['date'],
                    self.t('Input / output: ','Вход / выход: ')+count('inputTokens')+' / '+count('outputTokens'),
                    self.t('Cached input: ','Вход из кэша: ')+count('cachedInputTokens')+' · '+rate('cacheHitRate'),
                    self.t('Breakdown coverage: ','Охват детализации: ')+rate('counterCoverageRate')+self.t(' of observed tokens · partial',' наблюдаемых токенов · частично'),
                    self.t('Cache share does not measure subscription or skill savings.','Доля кэша не измеряет экономию подписки или пользу навыка.'),'']
            if 'local_tokens_backlog_skipped' in p.get('sourceStatus',[]):lines.append(self.t('Local backlog skipped; recent counters are partial, missing history is not reconstructed.','Локальное отставание пропущено; свежие счётчики частичны, пропущенная история не восстановлена.'))
        for d in self.data.get('history',[]):lines.append(f"{d['date']}  {d['provider']:10}  {d['tokens']:>12,.0f}")
        lines+=['',self.t('OBSERVED COVERAGE','НАБЛЮДАЕМЫЙ ОХВАТ')]
        checks=report.get('checkRuns')
        if checks:
            lines += [self.t('Helper results: ','Результаты помощников: ')+f"{checks['knownResults']} / {checks['runs']}",
                      self.t('Separate from native outcomes and human acceptance.','Отдельно от штатных исходов и приёмки человеком.')]
        health=report.get('storageHealth')
        if health:
            lines += [self.t('Journal quick integrity check: ','Быстрая проверка целостности журнала: ')+health['integrity'],
                      self.t('Analysis truncated: ','Анализ усечён: ')+str(health['analysisLimitReached'])]
        for c in report.get('coverage',[]):
            lines.append(f"{c['provider']}: {c['state']} · {c['pairedCalls']}/{c['calls']} · rejected {c['rejected']}")
            lines.append(self.t('Known results / unknown / collection gaps: ','Результат известен / неизвестен / пропуски: ')+f"{c.get('knownOutcomes','—')} / {c.get('unknownOutcomes','—')} / {c.get('collectionGaps','—')}")
        textview(overview,lines)
        lines=[self.t('Read ≠ invoked ≠ declared. No observation does not prove non-use.','Чтение ≠ вызов ≠ отметка. Отсутствие наблюдения не доказывает неиспользование.'),'']
        catalog=report.get('capabilities',[])
        observed=sum(r['loaded']+r['invoked']+r['declared']>0 for r in catalog)
        lines += [f"{len(catalog)} "+self.t('catalog entries','записей каталога')+f" · {observed} "+self.t('with evidence','с подтверждением'),self.t('Literal cat/sed/head/tail reads match registered paths only; reading does not prove application.','Буквальные cat/sed/head/tail учитываются по зарегистрированным путям; чтение не доказывает применение.'),'']
        for r in report.get('toolUsage',[]):
            lines.append(f"{r['provider']} · {r['tool']} · {r['calls']} "+self.t('calls','вызовов')+f" · {r['failed']} failed · {r['unknown']} unknown · {r['pending']} pending")
        for r in report.get('mcpNamespaces',[]):lines.append(f"{r['provider']} · MCP {r['namespace']} · {r['calls']}"+('' if r['registered'] else self.t(' · not registered',' · вне каталога')))
        lines+=['',self.t('REVIEWED SKILLS AND MCP','УЧТЁННЫЕ СКИЛЛЫ И MCP')]
        for r in sorted(catalog,key=lambda r:(-(r['loaded']+r['invoked']+r['declared']),r['provider'],r['id'])):
            evidence=f"{r['loaded']} "+self.t('loaded','чтений')+f" · {r['invoked']} "+self.t('invoked','вызовов')+f" · {r['declared']} "+self.t('declared','отметок') if r['loaded']+r['invoked']+r['declared'] else self.t('No confirmed events','Нет подтверждённых событий')
            lines += [f"{r['provider']} · {r['kind']} · {r['id']}",evidence,r['status']+('' if r['inventoryFresh'] else self.t(' · refresh inventory',' · обновите каталог')),'']
        asset_rows=report.get('efficiency',{}).get('assets',[])
        lines=[self.t('USEFUL RESULTS · reviewed selections; quotas stay separate','ПОЛЬЗА · проверенные выборки; лимиты отдельно'),'']+lines
        for r in asset_rows:
            def metric(key,percent=False):
                value=r.get(key)
                return '—' if value is None else f'{value*100:.1f}%' if percent else f'{value:,.1f}'
            lines += ['',f"{r['provider']} · {r['assetId']} · {r['version']}",
                      f"{r['accepted']}/{r['reviewed']} "+self.t('accepted','принято')+f" · {r['usageCompleteTasks']}/{r['tasks']} "+self.t('complete reported usage','с полным переданным расходом'),
                      self.t('Tokens / accepted: ','Токены / результат: ')+metric('tokensPerAccepted')+self.t(' · input from cache: ',' · вход из кэша: ')+metric('cacheHitRate',True),
                      self.t('Reported model requests: ','Передано вызовов модели: ')+metric('modelRequests'),
                      self.t('Median wall time, ms: ','Медиана времени, мс: ')+metric('medianElapsedMs')+f" · {r['elapsedTasks']}/{r['tasks']}",
                      f"{r['nativeIdentityUses']} "+self.t('name invocations','вызовов имени')+f" · {r['declaredUses']} "+self.t('version attestations','отметок версии')]
        lines += ['',self.t('Missing is unknown. Use and cache ratio do not prove subscription savings.','Пропуск неизвестен. Применение и доля кэша не доказывают экономию подписки.')]
        def write_metadata(action,spec):
            if self.fixture:return
            from efficiency import register_asset,record_task
            j=Journal(self.state)
            try:
                {'asset':register_asset,'task':record_task}[action](j,spec);self.refresh()
                messagebox.showinfo('Agent Pulse',self.t('Saved locally','Сохранено локально'),parent=w)
            except ValueError:messagebox.showerror('Agent Pulse',self.t('Check public labels, version and contiguous non-overlapping call selection.','Проверьте публичные метки, версию и последовательную непересекающуюся выборку вызовов.'),parent=w)
            finally:j.close()
        register=ttk.LabelFrame(capabilities,text=self.t('Register a version','Добавить версию'));register.pack(fill='x',padx=8,pady=4)
        asset_provider=tk.StringVar(value='codex');asset_kind=tk.StringVar(value='skill');asset_name=tk.StringVar();asset_version=tk.StringVar(value='v1');asset_finding=tk.StringVar()
        top=tk.Frame(register,bg=BG);top.pack(fill='x')
        for var,values in [(asset_provider,sorted(PROVIDERS)),(asset_kind,['skill','mcp','tool'])]:ttk.Combobox(top,textvariable=var,values=values,width=10,state='readonly').pack(side='left',padx=2)
        for title,var in [(self.t('Name','Имя'),asset_name),(self.t('Version','Версия'),asset_version)]:ttk.Label(top,text=title).pack(side='left');ttk.Entry(top,textvariable=var,width=16).pack(side='left',padx=2)
        bottom=tk.Frame(register,bg=BG);bottom.pack(fill='x')
        ttk.Label(bottom,text=self.t('Finding (optional)','Находка (необязательно)')).pack(side='left')
        ttk.Combobox(bottom,textvariable=asset_finding,values=['']+[r['id'] for r in report.get('findings',[])],width=32,state='readonly').pack(side='left')
        ttk.Button(bottom,text=self.t('Save version','Сохранить версию'),state='disabled' if self.fixture else 'normal',command=lambda:write_metadata('asset',{'provider':asset_provider.get(),'assetId':asset_name.get(),'version':asset_version.get(),'kind':asset_kind.get(),'findingId':asset_finding.get()})).pack(side='left',padx=3)
        textview(capabilities,lines)
        tk.Label(workflows,text=self.t('Suggestions need review; repeated does not mean waste.','Предложения требуют проверки; повтор не доказывает лишнюю работу.'),bg=BG,fg=QUIET,wraplength=670).pack(anchor='w',padx=8,pady=8)
        finder=ttk.Treeview(workflows,columns=('provider','repeats'),show='tree headings',height=7);finder.heading('#0',text=self.t('Workflow','Сценарий'));finder.heading('provider',text=self.t('Client','Клиент'));finder.heading('repeats',text=self.t('Occurrences','Повторы'));finder.column('provider',width=90,stretch=False);finder.column('repeats',width=80,stretch=False);finder.pack(fill='x',padx=8)
        findings=report.get('findings',[])
        for i,r in enumerate(findings):finder.insert('','end',iid=str(i),text=r['titleRu'] if self.language=='ru' else r['title'],values=(r['provider'],r['occurrences']))
        empty=self.t('No calls received. Configure observers in Settings and check native trust.','Вызовы не получены. Настройте наблюдатель и проверьте доверие клиента.') if not report.get('calls') else self.t('Calls are recorded; no repeat candidate meets the thresholds. Matching workflows need at least 3 turns. Other findings have separate thresholds.','Вызовы записываются; кандидаты пока не достигли порогов. Для одинаковых сценариев нужны минимум 3 хода. У других находок свои пороги.')
        health=[self.t('Silence can mean an idle client. Total coverage is unknown.','Тишина может означать простой клиента. Полный охват неизвестен.')]
        for c in report.get('coverage',[]):
            at=c.get('lastToolEventAt');last=datetime.fromtimestamp(at).strftime('%Y-%m-%d %H:%M:%S') if at else '—'
            health.append(f"{c['provider']} · {c['pairedCalls']}/{c['calls']} · "+self.t('last received: ','последний полученный: ')+last)
        controls=tk.Frame(workflows,bg=BG);controls.pack(fill='x',padx=8,pady=4)
        def mark(status,reason):
            if self.fixture or not finder.selection():return
            j=Journal(self.state)
            try:
                from finding_review import review_finding
                review_finding(j,findings[int(finder.selection()[0])]['id'],status,reason)
                self.refresh();w.destroy();self.analysis()
            except ValueError:messagebox.showerror('Agent Pulse',self.t('Decision was not saved; refresh the report.','Решение не сохранено; обновите отчёт.'),parent=w)
            finally:j.close()
        for title,status,reason in [(self.t('Script implemented','Внедрён скрипт'),'actioned','script'),(self.t('Skill implemented','Внедрён скилл'),'actioned','skill'),(self.t('Dismiss','Отклонить'),'dismissed','not-applicable'),(self.t('Reopen','Вернуть'),'open','unspecified')]:
            ttk.Button(controls,text=title,command=lambda st=status,re=reason:mark(st,re),state='disabled' if self.fixture else 'normal').pack(side='left',padx=2)
        for r in report.get('findingReviews',[]):health.append(f"{r['provider']} · {r['status']} · {r['recheckState']} · {r['windowHours']}h")
        if report.get('findingReviews'):health.append(self.t('Equal windows and partial coverage; no causal savings or resolution claim.','Равные окна и частичный охват; экономия и устранение не доказаны.'))
        def export_review():
            if self.fixture:return
            path=filedialog.asksaveasfilename(parent=w,defaultextension='.md',initialfile='agent-pulse-review.md',filetypes=[('Markdown','*.md')])
            if not path:return
            try:
                from journal import atomic_text
                from review_pack import markdown_pack
                atomic_text(Path(path),markdown_pack(report,self.language))
            except (ValueError,OSError):messagebox.showerror('Agent Pulse',self.t('Export failed','Экспорт не выполнен'),parent=w)
        ttk.Button(controls,text=self.t('Markdown','Отчёт MD'),command=export_review,state='disabled' if self.fixture else 'normal').pack(side='left',padx=2)
        info=textview(workflows,[self.t('Select a finding to inspect evidence.','Выберите наблюдение для просмотра примеров.') if findings else empty,'',*health])
        def finding_selected(_):
            if not finder.selection():return
            r=findings[int(finder.selection()[0])];calls=[c for c in report.get('recentCalls',[]) if c['id'] in r['evidenceIds']]
            models=', '.join(r.get('models',[])) or self.t('unknown','неизвестно')
            lines=[r['suggestionRu'] if self.language=='ru' else r['suggestion'],' → '.join(r['sequence']),' → '.join(r.get('operations',[])),r['inventoryStatus'],self.t('Models: ','Модели: ')+models+f" · {r.get('unknownModelCalls',0)} "+self.t('unknown calls','вызовов без модели'),self.t('No per-tool token estimate.','Токены каждому инструменту не приписываются.'),'']+[f"{c['tool']} · {c['template']} · {c['outcome']} · {c['durationMs']} ms · {c.get('outcomeSource','legacy')}\n  {c.get('model','other')} · {c.get('modelSource','not-reported')}" for c in calls]
            if not calls:lines.append(self.t('Use local MCP/CLI for evidence outside recent preview.','Примеры вне свежего списка доступны через локальный MCP/CLI.'))
            info.configure(state='normal');info.delete('1.0','end');info.insert('1.0','\n'.join(lines));info.configure(state='disabled')
        finder.bind('<<TreeviewSelect>>',finding_selected)
        tree=ttk.Treeview(sessions,columns=('calls','failed'),show='tree headings',height=6);tree.heading('#0',text=self.t('Session','Сессия'));tree.heading('calls',text=self.t('Calls','Вызовы'));tree.heading('failed',text=self.t('Failed','Ошибки'));tree.column('calls',width=70,stretch=False);tree.column('failed',width=70,stretch=False);tree.pack(fill='x',padx=8,pady=8)
        items=report.get('sessions',[])
        for i,r in enumerate(items):tree.insert('','end',iid=str(i),text=r['provider']+' · '+r['id'][:8],values=(r['calls'],r['failed']))
        row=tk.Frame(sessions,bg=BG);row.pack(fill='x',padx=8);label=tk.StringVar();variant=tk.StringVar(value='before');outcome=tk.StringVar(value='unknown')
        for title,var in [(self.t('Task label','Метка'),label),(self.t('Variant','Вариант'),variant)]:tk.Label(row,text=title,bg=BG,fg=FG).pack(side='left');ttk.Entry(row,textvariable=var,width=13).pack(side='left',padx=3)
        ttk.Combobox(row,textvariable=outcome,values=['unknown','accepted','failed','rework'],width=10,state='readonly').pack(side='left')
        review=ttk.LabelFrame(sessions,text=self.t('Review selected task · call numbers on this page','Оценить задачу · номера вызовов на странице'));review.pack(fill='x',padx=8,pady=4)
        task_first=tk.StringVar(value='1');task_last=tk.StringVar(value='1');criterion=tk.StringVar(value='quality-v1');task_asset=tk.StringVar();task_applied=tk.BooleanVar(value=False)
        task_assets={r['provider']+' · '+r['assetId']+' · '+r['version']:r for r in asset_rows}
        review_top=tk.Frame(review,bg=BG);review_top.pack(fill='x')
        for title,var,width in [(self.t('First','От'),task_first,4),(self.t('Last','До'),task_last,4),(self.t('Criterion','Критерий'),criterion,14)]:ttk.Label(review_top,text=title).pack(side='left');ttk.Entry(review_top,textvariable=var,width=width).pack(side='left',padx=3)
        asset_picker=ttk.Combobox(review_top,textvariable=task_asset,values=['']+list(task_assets),width=25,state='readonly');asset_picker.pack(side='left')
        review_bottom=tk.Frame(review,bg=BG);review_bottom.pack(fill='x')
        ttk.Checkbutton(review_bottom,text=self.t('I confirm this version was applied','Подтверждаю применение этой версии'),variable=task_applied).pack(side='left')
        def review_task():
            if self.fixture or not tree.selection():return
            try:
                first=int(task_first.get())-1;last=int(task_last.get());calls=page_state.get('calls',[])
                if not 0<=first<last<=len(calls):raise ValueError('invalid_selection')
                selected_calls=calls[first:last]
                spec={'provider':selected_calls[0]['provider'],'taskId':selected_calls[0]['id']+':'+selected_calls[-1]['id'],'label':label.get(),'variant':variant.get(),'criterion':criterion.get(),'outcome':outcome.get(),'callIds':[c['id'] for c in selected_calls]}
                if task_asset.get():
                    asset=task_assets[task_asset.get()];spec.update(assetId=asset['assetId'],version=asset['version'],applied=task_applied.get())
                elif task_applied.get():raise ValueError('asset_required')
                write_metadata('task',spec)
            except (ValueError,KeyError):messagebox.showerror('Agent Pulse',self.t('Check task boundaries and version','Проверьте границы задачи и версию'),parent=w)
        ttk.Button(review_bottom,text=self.t('Save task','Сохранить задачу'),command=review_task,state='disabled' if self.fixture else 'normal').pack(side='left',padx=3)
        detail=textview(sessions,[self.t('Select a session. Only sanitized metadata is shown.','Выберите сессию. Показываются только очищенные метаданные.')])
        pager=tk.Frame(sessions,bg=BG);pager.pack(fill='x',padx=8)
        position=tk.StringVar(value='');tk.Label(pager,textvariable=position,bg=BG,fg=QUIET).pack(side='left')
        page_state={'cursors':[None],'index':0,'next':None}
        def selected(_,reset=True):
            if not tree.selection():return
            r=items[int(tree.selection()[0])];label.set(r.get('label') or '');variant.set(r.get('variant') or 'before');outcome.set(r['outcome'])
            calls=[c for c in report.get('recentCalls',[]) if c['session']==r['id']]
            if reset:page_state.update(cursors=[None],index=0,next=None)
            from model_evidence import model_history
            history=r.get('modelHistory') or model_history(calls)
            if not self.fixture:
                j=Journal(self.state)
                try:
                    from session_view import session_page
                    value=session_page(j,r['id'],page_state['cursors'][page_state['index']])
                    calls=value['calls'];history=value['modelHistory'];page_state['next']=value['nextCursor'];page_state['cursors'][page_state['index']]=value['cursor']
                    position.set(f"{value['pageOffset']+1 if calls else 0}–{value['pageOffset']+len(calls)} / {value['callCount']}"+self.t(' · fixed snapshot',' · фиксированный снимок'))
                except ValueError:
                    position.set(self.t('Reopen session for a fresh snapshot','Откройте сессию заново для свежего снимка'));return
                finally:j.close()
            else:position.set(self.t('Demo preview only','Только демо-просмотр'))
            page_state['calls']=calls;task_first.set('1');task_last.set(str(max(1,len(calls))));task_asset.set('');task_applied.set(False)
            asset_picker.configure(values=['']+[key for key,asset in task_assets.items() if asset['provider']==r['provider']])
            previous.configure(state='normal' if not self.fixture and page_state['index']>0 else 'disabled')
            following.configure(state='normal' if not self.fixture and page_state['next'] else 'disabled')
            unknown=self.t('Unknown model','Модель неизвестна')
            transitions={'first-observed':'первое наблюдение','unknown-gap':'модель не передана','after-unknown':'после пропуска','timing-unverified':'порядок не подтверждён','overlapping-observations':'параллельные наблюдения','reported-change':'изменение в вызовах','same-reported-model':'та же модель'}
            def model_name(m):return unknown if m in (None,'other') else m
            def model_time(at):return datetime.fromtimestamp(at).strftime('%Y-%m-%d %H:%M:%S') if at is not None else '—'
            lines=[self.t('Observed model history','История наблюдаемых моделей'),
                   self.t('Times refer to calls, not exact UI switches. Unknowns are not inherited.','Время относится к вызовам, не к переключению в интерфейсе. Модель не угадывается.'),
                   f"{history['knownModelCalls']} / {history['knownModelCalls']+history['unknownModelCalls']} · "+self.t('identified calls','вызовов с моделью')]
            for s in history['segments']:
                transition=transitions.get(s['transition'],s['transition']) if self.language=='ru' else s['transition']
                lines.append(f"{model_name(s['model'])} · {s['calls']}\n  {model_time(s['firstObservedAt'])} → {model_time(s['lastObservedAt'])} · {transition}")
            if history['truncated']:lines.append(self.t('Last 100 segments; export for more.','Последние 100 участков; продолжение — в экспорте.'))
            lines += ['',self.t('Observed calls; wall times may overlap.','Наблюдаемые вызовы; времена могут пересекаться.'),'']+[f"{n+1}. {c['category']} · {c['tool']} · {c['outcome']}\n  {model_name(c.get('model'))} · {c.get('modelSource','not-reported')}\n  {c['template']}\n  {c['durationMs']} ms · {c['durationSource']}" for n,c in enumerate(calls)]
            detail.configure(state='normal');detail.delete('1.0','end');detail.insert('1.0','\n'.join(lines));detail.configure(state='disabled')
        tree.bind('<<TreeviewSelect>>',selected)
        def navigate(delta):
            if delta>0 and page_state['next']:
                page_state['cursors']=page_state['cursors'][:page_state['index']+1]+[page_state['next']]
            page_state['index']+=delta;selected(None,False)
        previous=ttk.Button(pager,text=self.t('Previous','Назад'),command=lambda:navigate(-1),state='disabled');previous.pack(side='right')
        following=ttk.Button(pager,text=self.t('Next','Далее'),command=lambda:navigate(1),state='disabled');following.pack(side='right',padx=3)
        def annotate():
            if self.fixture or not tree.selection():return
            j=Journal(self.state)
            try:j.annotate(items[int(tree.selection()[0])]['id'],label.get(),outcome.get(),variant.get());self.refresh()
            except ValueError:messagebox.showerror('Agent Pulse',self.t('Use nonsensitive ASCII labels without spaces.','Используйте нечувствительные ASCII-метки без пробелов.'))
            finally:j.close()
        ttk.Button(row,text=self.t('Save review','Сохранить'),command=annotate).pack(side='left',padx=3)
        tk.Label(comparison,text=self.t('Label at least 3 sessions per variant. Equal difficulty/model settings need review.','Отметьте хотя бы 3 сессии на вариант. Сложность задач и настройки модели проверяете вы.'),bg=BG,fg=QUIET,wraplength=670).pack(pady=10)
        labelled=sum(bool(r.get('label')) for r in items)
        tk.Label(comparison,text=f"{labelled} "+self.t('labelled sessions in this view. Empty groups mean insufficient evidence.','размеченных сессий в этом разделе. Пустые группы означают недостаток данных.'),bg=BG,fg=QUIET,wraplength=670).pack(pady=4)
        row=tk.Frame(comparison,bg=BG);row.pack(fill='x',padx=8);task=tk.StringVar();before=tk.StringVar(value='before');after=tk.StringVar(value='after')
        for var in [task,before,after]:ttk.Entry(row,textvariable=var,width=18).pack(side='left',padx=3)
        compare_tasks=tk.BooleanVar(value=True);compare_provider=tk.StringVar(value='codex')
        mode=tk.Frame(comparison,bg=BG);mode.pack(fill='x',padx=8)
        ttk.Checkbutton(mode,text=self.t('Compare reviewed tasks','Сравнивать отдельные задачи'),variable=compare_tasks).pack(side='left')
        ttk.Combobox(mode,textvariable=compare_provider,values=sorted(PROVIDERS),width=12,state='readonly').pack(side='left')
        tk.Label(mode,text=str(report.get('efficiency',{}).get('totalTasks',0))+self.t(' task selections',' выбранных задач'),bg=BG,fg=QUIET).pack(side='left',padx=8)
        result=textview(comparison,[self.t('Observational comparison only. No promised token saving or causal claim.','Сравнение наблюдений. Без обещаний экономии токенов и утверждений о причинности.')])
        def compare():
            if self.fixture:return
            j=Journal(self.state)
            try:
                from efficiency import compare_tasks as reviewed_comparison
                value=reviewed_comparison(j,task.get(),before.get(),after.get(),compare_provider.get()) if compare_tasks.get() else analytics.compare(j,task.get(),before.get(),after.get())
                result.configure(state='normal');result.delete('1.0','end');result.insert('1.0',json.dumps(value,ensure_ascii=False,indent=2));result.configure(state='disabled')
            except ValueError:messagebox.showerror('Agent Pulse',self.t('Invalid labels','Проверьте метки'))
            finally:j.close()
        ttk.Button(row,text=self.t('Compare','Сравнить'),command=compare).pack(side='left')
        if self.smoke:
            for index in range(len(book.tabs())):book.select(index);w.update_idletasks()
            for day in days:
                daytree.selection_set(day);day_selected()
                assert day+' · UTC' in daydetail.get('1.0','end')
                for p in self.data.get('providers',[]):assert p['id'].upper() in daydetail.get('1.0','end')
            if findings:finder.selection_set('0');finding_selected(None)
            if items:
                index=next((i for i,r in enumerate(items) if r.get('modelHistory',{}).get('reportedChanges',0)>0),0)
                tree.selection_set(str(index));selected(None)
                if any(r.get('modelHistory',{}).get('reportedChanges',0)>0 for r in items):
                    assert 'demo-' in detail.get('1.0','end'),'Model history must be rendered from fixture'
        book.select(selected_tab)
    def settings(self):
        if self.existing_utility('settings'):return
        w=self.window('Agent Pulse '+__version__+self.t(' · settings',' · настройки'));self.utility_windows['settings']=w
        canvas=tk.Canvas(w,bg=BG,highlightthickness=0);scroll=ttk.Scrollbar(w,command=canvas.yview);canvas.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');canvas.pack(fill='both',expand=True)
        f=tk.Frame(canvas,bg=BG);canvas.create_window(10,10,window=f,anchor='nw');f.bind('<Configure>',lambda e:canvas.configure(scrollregion=canvas.bbox('all')))
        def label(s):tk.Label(f,text=s,bg=BG,fg=FG,anchor='w').pack(fill='x',pady=6)
        lang=tk.StringVar(value=self.language);ttk.Combobox(f,textvariable=lang,values=['en','ru'],state='readonly').pack(anchor='w')
        startup=tk.BooleanVar(value=False)
        startup_message=tk.StringVar(value=self.t('Demo: startup settings are unchanged.','Демо: автозапуск не меняется.') if self.fixture else self.t('For your account. Windows startup settings can also block this item.','Для вашей учётной записи. Windows также может отключить этот пункт в настройках автозагрузки.'))
        def read_startup():
            if self.fixture or sys.platform!='win32':return
            try:startup.set(windows_launch_at_login())
            except (OSError,ValueError):startup_message.set(self.t('Could not read startup settings.','Не удалось прочитать настройки автозапуска.'))
        def change_startup():
            if self.fixture or sys.platform!='win32':return
            try:startup.set(windows_launch_at_login(startup.get()))
            except (OSError,ValueError):
                read_startup();startup_message.set(self.t('Could not change startup settings.','Не удалось изменить автозапуск.'))
        read_startup()
        tk.Checkbutton(f,text=self.t('Launch at login','Запускать при входе в систему'),variable=startup,command=change_startup,state='disabled' if self.fixture or sys.platform!='win32' else 'normal',bg=BG,fg=FG,selectcolor=BG).pack(anchor='w')
        tk.Label(f,textvariable=startup_message,bg=BG,fg=QUIET,wraplength=510,justify='left').pack(anchor='w',pady=4)
        w.bind('<FocusIn>',lambda e:read_startup() if e.widget is w else None,add='+')
        top=tk.BooleanVar(value=True);tk.Checkbutton(f,text=self.t('Always on top','Поверх окон'),variable=top,command=lambda:self.save_topmost(top.get()),bg=BG,fg=FG,selectcolor=BG).pack(anchor='w')
        label(self.t('Widget size · or drag the lower-right corner','Размер виджета · можно тянуть за нижний правый угол'))
        size=tk.DoubleVar(value=self.scale)
        presets=tk.Frame(f,bg=BG);presets.pack(anchor='w')
        for value in (.8,.9,1):ttk.Button(presets,text=f'{round(value*100)}%',command=lambda v=value:(size.set(v),self.set_scale(v))).pack(side='left')
        ttk.Scale(f,from_=.8,to=1,variable=size,command=lambda v:self.set_scale(float(v),save=False)).pack(fill='x')
        label(self.t('Placement · tray icon opens the full widget','Размещение · значок в трее открывает полное табло'))
        placement=tk.StringVar(value=self.display_mode)
        ttk.Combobox(f,textvariable=placement,values=['floating','compact','tray'],state='readonly').pack(anchor='w')
        label(self.t('Compact keeps quota rows above the taskbar. Tray shows a bounded tooltip; Windows may hide its icon.','Compact — проценты над панелью задач. Tray — подсказка при наведении; значок может быть скрыт Windows.'))
        def key_controls(ident,title):
            label(title)
            region=tk.StringVar(value='kimi.com')
            if ident=='kimi':
                label(self.t('Kimi key region','Регион ключа Kimi'))
                ttk.Combobox(f,textvariable=region,values=['kimi.com','kimi.ai'],state='readonly').pack(anchor='w')
            key=tk.StringVar();ttk.Entry(f,textvariable=key,show='•',width=40).pack(anchor='w')
            def save(remove=False):
                if self.fixture:return
                try:
                    from provider_secrets import save_key
                    save_key(self.state,'' if remove else key.get(),ident,'global' if ident=='kimi' and region.get()=='kimi.ai' else 'mainland-cn');key.set('');self.auth_revision+=1
                    for provider in self.data.get('providers',[]):
                        if provider['id']==ident:provider.update(quotas=[],quotaObservedAt=None,status='unavailable')
                    self.render();self.refresh()
                except Exception:messagebox.showerror('Agent Pulse',self.t('Could not save provider key','Не удалось сохранить ключ провайдера'))
            ttk.Button(f,text=self.t('Save key','Сохранить ключ'),command=save).pack(anchor='w')
            ttk.Button(f,text=self.t('Disconnect quotas','Отключить квоты'),command=lambda:save(True)).pack(anchor='w')
        key_controls('glm','GLM Coding Plan · Z.ai')
        key_controls('kimi','Kimi Code · API key')
        label(self.t('Own keys stay in private Secrets.json. Native credentials are not read. Kimi Chat/Work login is not a Kimi Code key; quotas are not token spend.','Ключи — только в закрытом Secrets.json. Ключи приложений не читаются. Вход в Kimi Chat/Work не заменяет ключ Kimi Code; квоты не равны расходу токенов.'))
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
                update_settings(self.state,{'enabledProviders':[i for i,v in flags.items() if v.get()],'localPatterns':patterns.get(),'localTokens':tokens.get(),'language':self.language})
            self.refresh();w.destroy()
        ttk.Button(f,text=self.t('Apply','Применить'),command=apply).pack(anchor='w',pady=10)
        label(self.t('Local observers · start a new client session after setup','Локальные наблюдатели · после настройки начните новую сессию'))
        def observer(provider,enabled):
            if self.fixture:return
            try:
                instrumentation.configure_hooks(provider,self.state,enabled)
                messagebox.showinfo('Agent Pulse',self.t('Configured. Start a new session; native hook trust review may be required.','Настроено. Начните новую сессию; клиент может запросить доверие хуку.'))
            except Exception:messagebox.showerror('Agent Pulse',self.t('Configuration failed','Настройка не удалась'))
        for provider in ['codex','glm','claude','kimi']:
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
