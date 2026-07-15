import { RequireAuth } from '@/hooks/use-auth';
import { Layout } from '@/components/layout';
import { 
  useGetBotSettings, 
  useUpdateBotSettings, 
  useRestartBot, 
  useSendAnnouncement,
  BotSettingsUpdateStatusType
} from '@workspace/api-client-react';
import { useState, useEffect } from 'react';
import { Power, Send, AlertTriangle } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function Settings() {
  const { data: settings, refetch } = useGetBotSettings();
  const updateSettings = useUpdateBotSettings();
  const restartBot = useRestartBot();
  const sendAnnouncement = useSendAnnouncement();

  const [statusText, setStatusText] = useState('');
  const [statusType, setStatusType] = useState<BotSettingsUpdateStatusType>('playing');
  const [announcementMsg, setAnnouncementMsg] = useState('');

  useEffect(() => {
    if (settings) {
      setStatusText(settings.statusText);
      setStatusType(settings.statusType);
    }
  }, [settings]);

  const handleSaveStatus = () => {
    updateSettings.mutate({
      data: { statusText, statusType }
    }, { onSuccess: () => refetch() });
  };

  const handleMaintenanceToggle = () => {
    if (!settings) return;
    updateSettings.mutate({
      data: { maintenanceMode: !settings.maintenanceMode }
    }, { onSuccess: () => refetch() });
  };

  const handleRestart = () => {
    if (!window.confirm("WARNING: This will drop all active connections and restart the bot process. Continue?")) return;
    restartBot.mutate(undefined);
  };

  const handleSendAnnouncement = () => {
    if (!announcementMsg) return;
    if (!window.confirm("Broadcast this message to all servers?")) return;
    
    sendAnnouncement.mutate({
      data: { message: announcementMsg }
    }, {
      onSuccess: () => setAnnouncementMsg('')
    });
  };

  return (
    <RequireAuth>
      <Layout>
        <div className="p-8 space-y-8 max-w-[1000px] mx-auto">
          <header>
            <h1 className="text-2xl font-bold tracking-widest text-foreground uppercase mb-2">System Configuration</h1>
            <div className="h-px w-full bg-gradient-to-r from-primary/50 to-transparent" />
          </header>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            
            {/* Core Controls */}
            <div className="space-y-8">
              <div className="glass-panel p-6 border-destructive/20 relative overflow-hidden group">
                <div className="absolute inset-0 bg-destructive/5 opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none" />
                <h2 className="text-sm font-mono text-destructive tracking-widest uppercase mb-4 flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4" /> Power Controls
                </h2>
                
                <div className="space-y-4">
                  <div className="flex items-center justify-between p-4 bg-black/40 border border-border">
                    <div>
                      <div className="font-mono text-foreground uppercase">Maintenance Mode</div>
                      <div className="text-xs text-muted-foreground mt-1">Locks all commands to owner only</div>
                    </div>
                    <button
                      onClick={handleMaintenanceToggle}
                      className={cn(
                        "px-4 py-2 font-mono text-xs uppercase tracking-widest transition-all border",
                        settings?.maintenanceMode 
                          ? "bg-destructive/20 text-destructive border-destructive" 
                          : "bg-black text-muted-foreground border-border hover:border-primary"
                      )}
                    >
                      {settings?.maintenanceMode ? 'ACTIVE' : 'INACTIVE'}
                    </button>
                  </div>

                  <button
                    onClick={handleRestart}
                    className="w-full p-4 flex items-center justify-center gap-3 bg-destructive/10 text-destructive border border-destructive/30 hover:bg-destructive hover:text-black transition-all font-mono uppercase tracking-widest"
                  >
                    <Power className="w-4 h-4" /> Force Restart
                  </button>
                </div>
              </div>

              {/* Status Update */}
              <div className="glass-panel p-6">
                <h2 className="text-sm font-mono text-primary tracking-widest uppercase mb-4">Presence Configuration</h2>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-2">
                    {(['playing', 'watching', 'listening', 'streaming'] as BotSettingsUpdateStatusType[]).map(type => (
                      <button
                        key={type}
                        onClick={() => setStatusType(type)}
                        className={cn(
                          "py-2 px-3 font-mono text-xs uppercase tracking-widest transition-colors border",
                          statusType === type 
                            ? "bg-primary/20 text-primary border-primary" 
                            : "bg-black text-muted-foreground border-border hover:border-primary/50"
                        )}
                      >
                        {type}
                      </button>
                    ))}
                  </div>
                  <input
                    value={statusText}
                    onChange={e => setStatusText(e.target.value)}
                    placeholder="ENTER_PRESENCE_TEXT..."
                    className="w-full bg-black border border-primary/30 text-foreground font-mono px-4 py-3 focus:outline-none focus:border-primary transition-colors placeholder:text-muted-foreground placeholder:tracking-widest uppercase"
                  />
                  <button
                    onClick={handleSaveStatus}
                    className="w-full bg-primary/20 text-primary border border-primary/50 py-3 font-mono uppercase tracking-widest hover:bg-primary hover:text-black transition-all"
                  >
                    Update Presence
                  </button>
                </div>
              </div>
            </div>

            {/* Broadcast */}
            <div className="space-y-8">
              <div className="glass-panel p-6 h-full flex flex-col">
                <h2 className="text-sm font-mono text-primary tracking-widest uppercase mb-4">Global Broadcast</h2>
                <p className="text-xs text-muted-foreground mb-4 font-mono">
                  Transmits message to the default channel of all connected guilds. Use with extreme caution.
                </p>
                <textarea
                  value={announcementMsg}
                  onChange={e => setAnnouncementMsg(e.target.value)}
                  placeholder="COMPOSE_BROADCAST..."
                  className="w-full flex-1 min-h-[200px] bg-black border border-primary/30 text-foreground font-mono px-4 py-3 focus:outline-none focus:border-primary transition-colors placeholder:text-muted-foreground placeholder:tracking-widest resize-none"
                />
                <button
                  onClick={handleSendAnnouncement}
                  disabled={!announcementMsg}
                  className="w-full mt-4 bg-primary/10 text-primary border border-primary/50 py-4 font-mono uppercase tracking-widest hover:bg-primary/30 hover:shadow-[0_0_15px_rgba(0,255,136,0.3)] transition-all flex items-center justify-center gap-3 disabled:opacity-50 disabled:pointer-events-none"
                >
                  <Send className="w-4 h-4" /> Transmit
                </button>
              </div>
            </div>

          </div>
        </div>
      </Layout>
    </RequireAuth>
  );
}
