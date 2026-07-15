import { useAuth } from '@/hooks/use-auth';
import { Link, useLocation } from 'wouter';
import { useLogout } from '@workspace/api-client-react';
import { 
  Terminal, 
  Server, 
  ShieldBan, 
  ScrollText, 
  Cpu, 
  BarChart, 
  Settings, 
  LogOut 
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useGetBotStats, getGetBotStatsQueryKey } from '@workspace/api-client-react';

export function Layout({ children }: { children: React.ReactNode }) {
  const { user } = useAuth();
  const [location, setLocation] = useLocation();
  const logout = useLogout();
  
  const { data: stats } = useGetBotStats({ query: { refetchInterval: 10000, queryKey: getGetBotStatsQueryKey() } });

  const navItems = [
    { href: '/dashboard', label: 'DASHBOARD', icon: Terminal },
    { href: '/servers', label: 'SERVERS', icon: Server },
    { href: '/blacklist', label: 'BLACKLIST', icon: ShieldBan },
    { href: '/logs', label: 'LOGS', icon: ScrollText },
    { href: '/commands', label: 'COMMANDS', icon: Cpu },
    { href: '/stats', label: 'STATS', icon: BarChart },
    { href: '/settings', label: 'SETTINGS', icon: Settings },
  ];

  const handleLogout = () => {
    logout.mutate(undefined, {
      onSuccess: () => {
        setLocation('/');
      }
    });
  };

  return (
    <div className="min-h-[100dvh] flex bg-background text-foreground relative overflow-hidden">
      <div className="scanline" />
      
      {/* Sidebar */}
      <aside className="w-64 border-r border-border bg-card/50 flex flex-col relative z-10 glass-panel">
        <div className="p-6 border-b border-border">
          <div className="flex items-center justify-between mb-4">
            <h1 className="font-bold text-xl tracking-widest text-primary glitch-hover uppercase">FMD_SYS</h1>
            <div className="flex items-center gap-2">
              <span className={cn(
                "w-2 h-2 rounded-full animate-pulse",
                stats?.status === 'online' ? "bg-primary shadow-[0_0_8px_var(--primary)]" : "bg-destructive"
              )} />
            </div>
          </div>
          <div className="text-xs font-mono text-muted-foreground uppercase tracking-widest">
            {stats?.status === 'online' ? 'STATUS: NOMINAL' : 'STATUS: OFFLINE'}
          </div>
        </div>

        <nav className="flex-1 py-6 px-4 space-y-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location === item.href || (location.startsWith(item.href) && item.href !== '/');
            
            return (
              <Link key={item.href} href={item.href} className="block">
                <div className={cn(
                  "flex items-center gap-3 px-4 py-3 text-sm font-mono tracking-widest transition-all duration-200 uppercase",
                  isActive 
                    ? "bg-primary/10 text-primary border border-primary/30 glow-border" 
                    : "text-muted-foreground hover:text-foreground hover:bg-white/5 border border-transparent"
                )}>
                  <Icon className="w-4 h-4" />
                  {item.label}
                </div>
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-border mt-auto">
          <div className="flex items-center gap-3 p-3 bg-black/40 border border-border">
            {user?.avatar ? (
              <img src={`https://cdn.discordapp.com/avatars/${user.id}/${user.avatar}.png`} alt="Avatar" className="w-10 h-10 border border-primary/30" />
            ) : (
              <div className="w-10 h-10 bg-primary/20 border border-primary/50 flex items-center justify-center font-mono text-primary">
                {user?.username?.[0]?.toUpperCase()}
              </div>
            )}
            <div className="flex-1 min-w-0">
              <div className="font-mono text-sm text-primary truncate">{user?.username}</div>
              <div className="font-mono text-xs text-muted-foreground truncate">ID: {user?.id}</div>
            </div>
            <button 
              onClick={handleLogout}
              className="p-2 text-muted-foreground hover:text-destructive transition-colors"
              title="Logout"
            >
              <LogOut className="w-4 h-4" />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 relative z-10 overflow-y-auto bg-gradient-to-br from-background to-black/90">
        {children}
      </main>
    </div>
  );
}
