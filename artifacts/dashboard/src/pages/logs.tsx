import { RequireAuth } from '@/hooks/use-auth';
import { Layout } from '@/components/layout';
import { useListLogs, getListLogsQueryKey, ListLogsType } from '@workspace/api-client-react';
import { useState } from 'react';
import { Filter, Search } from 'lucide-react';
import { cn } from '@/lib/utils';

const LOG_TYPES: ListLogsType[] = ['command', 'error', 'join', 'leave', 'moderation', 'api'];

export default function Logs() {
  const [search, setSearch] = useState('');
  const [type, setType] = useState<ListLogsType | ''>('');
  
  const { data } = useListLogs({ search, type: type || undefined, limit: 100 }, { query: { refetchInterval: 5000, queryKey: getListLogsQueryKey({ search, type: type || undefined, limit: 100 }) } });

  return (
    <RequireAuth>
      <Layout>
        <div className="p-8 space-y-6 max-w-[1600px] mx-auto h-[100dvh] flex flex-col">
          <header className="flex items-center justify-between shrink-0">
            <h1 className="text-2xl font-bold tracking-widest text-foreground uppercase">System Audit Log</h1>
            <div className="flex items-center gap-4">
              <div className="flex gap-2 bg-black/50 border border-border p-1">
                <button
                  onClick={() => setType('')}
                  className={cn("px-3 py-1 font-mono text-xs uppercase transition-colors", type === '' ? 'bg-primary text-black' : 'text-muted-foreground hover:text-foreground')}
                >
                  ALL
                </button>
                {LOG_TYPES.map(t => (
                  <button
                    key={t}
                    onClick={() => setType(t)}
                    className={cn("px-3 py-1 font-mono text-xs uppercase transition-colors", type === t ? 'bg-primary text-black' : 'text-muted-foreground hover:text-foreground')}
                  >
                    {t}
                  </button>
                ))}
              </div>
              <div className="relative w-64">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-primary" />
                <input 
                  value={search}
                  onChange={e => setSearch(e.target.value)}
                  placeholder="QUERY_LOGS..."
                  className="w-full bg-black/50 border border-primary/30 text-foreground font-mono pl-10 pr-4 py-1.5 focus:outline-none focus:border-primary transition-colors placeholder:text-muted-foreground placeholder:tracking-widest uppercase text-sm"
                />
              </div>
            </div>
          </header>

          <div className="glass-panel flex-1 overflow-hidden flex flex-col min-h-0">
            <div className="flex-1 overflow-auto p-4 space-y-1 font-mono text-sm">
              {data?.logs.map((log) => {
                const colors: Record<string, string> = {
                  command: 'text-blue-400',
                  error: 'text-destructive',
                  join: 'text-primary',
                  leave: 'text-orange-400',
                  moderation: 'text-yellow-400',
                  api: 'text-purple-400'
                };
                return (
                  <div key={log.id} className="flex flex-wrap md:flex-nowrap gap-x-4 gap-y-1 p-2 hover:bg-white/5 border border-transparent hover:border-white/10 transition-colors">
                    <span className="text-muted-foreground w-[180px] shrink-0">{new Date(log.createdAt).toLocaleString()}</span>
                    <span className={cn("w-28 shrink-0 uppercase", colors[log.type] || 'text-foreground')}>[{log.type}]</span>
                    <span className="text-foreground flex-1 break-all md:break-normal">{log.message}</span>
                    <div className="w-full md:w-auto flex gap-4 text-xs text-muted-foreground shrink-0 justify-end md:justify-start">
                      {log.userId && <span>USR: {log.userId}</span>}
                      {log.guildId && <span>GLD: {log.guildId}</span>}
                    </div>
                  </div>
                );
              })}
              {data?.logs.length === 0 && (
                <div className="text-center text-muted-foreground py-10 uppercase tracking-widest">
                  NO_RECORDS_MATCH_QUERY
                </div>
              )}
            </div>
            <div className="p-2 bg-black/80 border-t border-border flex justify-between items-center text-xs font-mono text-primary uppercase shrink-0">
              <span>SCANNING LIVE FEED...</span>
              <span>Displaying {data?.logs.length || 0} Records</span>
            </div>
          </div>
        </div>
      </Layout>
    </RequireAuth>
  );
}
