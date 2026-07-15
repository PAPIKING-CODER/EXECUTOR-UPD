import { RequireAuth } from '@/hooks/use-auth';
import { Layout } from '@/components/layout';
import { useGetBotStats, getGetBotStatsQueryKey, useListLogs, getListLogsQueryKey } from '@workspace/api-client-react';
import { formatUptime, formatBytes, formatNumber } from '@/lib/utils';
import { motion } from 'framer-motion';
import { Server, Users, Hash, Cpu, MemoryStick, Activity, ShieldAlert, Zap } from 'lucide-react';
import { cn } from '@/lib/utils';

function StatCard({ title, value, icon: Icon, delay = 0 }: { title: string, value: string | number, icon: any, delay?: number }) {
  return (
    <motion.div 
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, delay }}
      className="glass-panel p-5 relative overflow-hidden group"
    >
      <div className="absolute right-0 top-0 w-24 h-24 bg-primary/5 rounded-full blur-2xl -mr-10 -mt-10 transition-transform group-hover:scale-150" />
      <div className="flex items-start justify-between relative z-10">
        <div className="space-y-4">
          <div className="text-xs font-mono text-muted-foreground uppercase tracking-widest">{title}</div>
          <div className="text-2xl font-mono text-foreground">{value}</div>
        </div>
        <div className="p-3 bg-black/40 border border-border/50 text-primary">
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </motion.div>
  );
}

export default function Dashboard() {
  const { data: stats } = useGetBotStats({ query: { refetchInterval: 10000, queryKey: getGetBotStatsQueryKey() } });
  const { data: logs } = useListLogs({ limit: 10 }, { query: { refetchInterval: 10000, queryKey: getListLogsQueryKey({ limit: 10 }) } });

  return (
    <RequireAuth>
      <Layout>
        <div className="p-8 space-y-8 max-w-[1600px] mx-auto">
          <header>
            <h1 className="text-2xl font-bold tracking-widest text-foreground uppercase mb-2">System Overview</h1>
            <div className="h-px w-full bg-gradient-to-r from-primary/50 to-transparent" />
          </header>

          {stats && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard title="Uptime" value={formatUptime(stats.uptime)} icon={Activity} delay={0.1} />
              <StatCard title="Latency" value={`${stats.latency}ms`} icon={Zap} delay={0.2} />
              <StatCard title="Guilds" value={formatNumber(stats.guildCount)} icon={Server} delay={0.3} />
              <StatCard title="Users" value={formatNumber(stats.userCount)} icon={Users} delay={0.4} />
              
              <StatCard title="Channels" value={formatNumber(stats.channelCount)} icon={Hash} delay={0.5} />
              <StatCard title="CPU Usage" value={`${stats.cpuUsage.toFixed(1)}%`} icon={Cpu} delay={0.6} />
              <StatCard title="Memory" value={`${formatBytes(stats.ramUsage)} / ${formatBytes(stats.ramTotal)}`} icon={MemoryStick} delay={0.7} />
              <StatCard title="Discord API" value={stats.discordApiStatus.toUpperCase()} icon={ShieldAlert} delay={0.8} />
            </div>
          )}

          <div className="glass-panel mt-8 flex flex-col">
            <div className="p-4 border-b border-border bg-black/40">
              <h2 className="text-sm font-mono tracking-widest uppercase text-primary">Live Data Stream</h2>
            </div>
            <div className="p-4 space-y-2 h-[400px] overflow-y-auto font-mono text-sm">
              {logs?.logs.map((log) => {
                const colors = {
                  command: 'text-blue-400',
                  error: 'text-destructive',
                  join: 'text-primary',
                  leave: 'text-orange-400',
                  moderation: 'text-yellow-400',
                  api: 'text-purple-400'
                };
                return (
                  <div key={log.id} className="flex gap-4 p-2 hover:bg-white/5 border border-transparent hover:border-white/10 transition-colors">
                    <span className="text-muted-foreground w-24 shrink-0">{new Date(log.createdAt).toLocaleTimeString()}</span>
                    <span className={cn("w-28 shrink-0 uppercase", colors[log.type])}>[{log.type}]</span>
                    <span className="text-foreground">{log.message}</span>
                  </div>
                );
              })}
              {!logs?.logs?.length && (
                <div className="text-muted-foreground italic p-4">No recent activity detected.</div>
              )}
            </div>
          </div>
        </div>
      </Layout>
    </RequireAuth>
  );
}
