import { RequireAuth } from '@/hooks/use-auth';
import { Layout } from '@/components/layout';
import { useGetStatsOverview, useGetTopCommands } from '@workspace/api-client-react';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  BarChart, Bar
} from 'recharts';

export default function Stats() {
  const { data: overview } = useGetStatsOverview();
  const { data: topCommands } = useGetTopCommands();

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-black/90 border border-primary/30 p-3 font-mono">
          <p className="text-muted-foreground text-xs mb-1">{label}</p>
          <p className="text-primary">{payload[0].value}</p>
        </div>
      );
    }
    return null;
  };

  return (
    <RequireAuth>
      <Layout>
        <div className="p-8 space-y-8 max-w-[1600px] mx-auto">
          <header>
            <h1 className="text-2xl font-bold tracking-widest text-foreground uppercase mb-2">Telemetry & Metrics</h1>
            <div className="h-px w-full bg-gradient-to-r from-primary/50 to-transparent" />
          </header>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="glass-panel p-6">
              <h2 className="text-sm font-mono text-primary tracking-widest uppercase mb-6">Server Growth</h2>
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={overview?.serverGrowth}>
                    <defs>
                      <linearGradient id="colorGreen" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="hsl(152, 100%, 50%)" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="hsl(152, 100%, 50%)" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
                    <XAxis dataKey="date" stroke="rgba(255,255,255,0.3)" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke="rgba(255,255,255,0.3)" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Area type="monotone" dataKey="value" stroke="hsl(152, 100%, 50%)" strokeWidth={2} fillOpacity={1} fill="url(#colorGreen)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="glass-panel p-6">
              <h2 className="text-sm font-mono text-primary tracking-widest uppercase mb-6">User Growth</h2>
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={overview?.userGrowth}>
                    <defs>
                      <linearGradient id="colorBlue" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="hsl(200, 100%, 50%)" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="hsl(200, 100%, 50%)" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" vertical={false} />
                    <XAxis dataKey="date" stroke="rgba(255,255,255,0.3)" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis stroke="rgba(255,255,255,0.3)" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip content={<CustomTooltip />} />
                    <Area type="monotone" dataKey="value" stroke="hsl(200, 100%, 50%)" strokeWidth={2} fillOpacity={1} fill="url(#colorBlue)" />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="glass-panel p-6 lg:col-span-2">
              <h2 className="text-sm font-mono text-primary tracking-widest uppercase mb-6">Top Directives Executed</h2>
              <div className="h-[300px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={topCommands} layout="vertical" margin={{ left: 50 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" horizontal={false} />
                    <XAxis type="number" stroke="rgba(255,255,255,0.3)" fontSize={12} tickLine={false} axisLine={false} />
                    <YAxis dataKey="name" type="category" stroke="rgba(255,255,255,0.8)" fontSize={12} tickLine={false} axisLine={false} />
                    <Tooltip content={<CustomTooltip />} cursor={{fill: 'rgba(255,255,255,0.05)'}} />
                    <Bar dataKey="count" fill="hsl(152, 100%, 50%)" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </div>
          </div>
        </div>
      </Layout>
    </RequireAuth>
  );
}
