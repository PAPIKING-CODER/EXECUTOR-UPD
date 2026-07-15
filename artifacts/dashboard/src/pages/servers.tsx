import { RequireAuth } from '@/hooks/use-auth';
import { Layout } from '@/components/layout';
import { useListGuilds, useLeaveGuild } from '@workspace/api-client-react';
import { formatNumber } from '@/lib/utils';
import { useState } from 'react';
import { Search, LogOut, ShieldAlert } from 'lucide-react';
import { toast } from 'sonner';
import { motion } from 'framer-motion';

export default function Servers() {
  const [search, setSearch] = useState('');
  const { data, refetch } = useListGuilds({ search, limit: 100 });
  const leaveGuild = useLeaveGuild();

  const handleLeave = (id: string, name: string) => {
    if (!window.confirm(`Initiate protocol to leave guild: ${name}?`)) return;
    
    leaveGuild.mutate({ guildId: id }, {
      onSuccess: () => {
        toast.success(`Left guild ${name}`);
        refetch();
      },
      onError: () => {
        toast.error("Failed to leave guild");
      }
    });
  };

  return (
    <RequireAuth>
      <Layout>
        <div className="p-8 space-y-6 max-w-[1600px] mx-auto">
          <header className="flex items-center justify-between">
            <h1 className="text-2xl font-bold tracking-widest text-foreground uppercase">Server Matrix</h1>
            <div className="relative w-72">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-primary" />
              <input 
                type="text" 
                placeholder="SEARCH_GUILDS..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full bg-black/50 border border-primary/30 text-foreground font-mono pl-10 pr-4 py-2 focus:outline-none focus:border-primary transition-colors placeholder:text-muted-foreground placeholder:tracking-widest uppercase"
              />
            </div>
          </header>

          <div className="glass-panel">
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="bg-black/60 border-b border-border text-xs font-mono tracking-widest text-primary uppercase">
                    <th className="p-4 font-normal">Icon</th>
                    <th className="p-4 font-normal">Name</th>
                    <th className="p-4 font-normal">ID</th>
                    <th className="p-4 font-normal text-right">Members</th>
                    <th className="p-4 font-normal">Joined</th>
                    <th className="p-4 font-normal text-center">Actions</th>
                  </tr>
                </thead>
                <tbody className="font-mono text-sm">
                  {data?.guilds.map((guild, i) => (
                    <motion.tr 
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: i * 0.05 }}
                      key={guild.id} 
                      className="border-b border-white/5 hover:bg-white/5 transition-colors group"
                    >
                      <td className="p-4 w-16">
                        {guild.icon ? (
                          <img src={`https://cdn.discordapp.com/icons/${guild.id}/${guild.icon}.png`} className="w-10 h-10 border border-border" alt="" />
                        ) : (
                          <div className="w-10 h-10 bg-black border border-border flex items-center justify-center text-muted-foreground">
                            {guild.name[0]}
                          </div>
                        )}
                      </td>
                      <td className="p-4 font-sans text-base text-foreground font-medium">{guild.name}</td>
                      <td className="p-4 text-muted-foreground">{guild.id}</td>
                      <td className="p-4 text-right">{formatNumber(guild.memberCount)}</td>
                      <td className="p-4 text-muted-foreground">{guild.joinedAt ? new Date(guild.joinedAt).toLocaleDateString() : 'N/A'}</td>
                      <td className="p-4 text-center">
                        <button 
                          onClick={() => handleLeave(guild.id, guild.name)}
                          className="p-2 text-destructive hover:bg-destructive/10 border border-transparent hover:border-destructive/30 transition-all opacity-0 group-hover:opacity-100"
                          title="Leave Server"
                        >
                          <LogOut className="w-4 h-4" />
                        </button>
                      </td>
                    </motion.tr>
                  ))}
                  {data?.guilds.length === 0 && (
                    <tr>
                      <td colSpan={6} className="p-8 text-center text-muted-foreground font-mono">
                        NO_DATA_FOUND
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="p-4 bg-black/40 border-t border-border flex justify-between items-center text-xs font-mono text-muted-foreground uppercase">
              <span>Total Entries: {data?.total || 0}</span>
              <span>Page {data?.page || 1}</span>
            </div>
          </div>
        </div>
      </Layout>
    </RequireAuth>
  );
}
