import { RequireAuth } from '@/hooks/use-auth';
import { Layout } from '@/components/layout';
import { useListCommands, useUpdateCommand } from '@workspace/api-client-react';
import { formatNumber } from '@/lib/utils';

export default function Commands() {
  const { data, refetch } = useListCommands();
  const updateCommand = useUpdateCommand();

  const handleToggle = (name: string, enabled: boolean) => {
    updateCommand.mutate(
      { name, data: { enabled: !enabled } },
      { onSuccess: () => refetch() }
    );
  };

  const categories = Array.from(new Set(data?.map(c => c.category) || []));

  return (
    <RequireAuth>
      <Layout>
        <div className="p-8 space-y-8 max-w-[1600px] mx-auto">
          <header>
            <h1 className="text-2xl font-bold tracking-widest text-foreground uppercase mb-2">Command Directives</h1>
            <div className="h-px w-full bg-gradient-to-r from-primary/50 to-transparent" />
          </header>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {categories.map(category => (
              <div key={category} className="space-y-4">
                <h2 className="text-primary font-mono tracking-widest uppercase px-2 bg-primary/10 border-l-2 border-primary py-1">
                  [{category}]
                </h2>
                <div className="space-y-3">
                  {data?.filter(c => c.category === category).map(cmd => (
                    <div key={cmd.name} className="glass-panel p-4 hover:border-primary/40 transition-colors">
                      <div className="flex justify-between items-start mb-2">
                        <div className="font-mono text-lg text-foreground">/{cmd.name}</div>
                        <button
                          onClick={() => handleToggle(cmd.name, cmd.enabled)}
                          className={`w-12 h-6 rounded-none border flex items-center transition-colors ${
                            cmd.enabled 
                            ? 'bg-primary/20 border-primary justify-end pr-1' 
                            : 'bg-black border-muted-foreground justify-start pl-1'
                          }`}
                        >
                          <div className={`w-4 h-4 ${cmd.enabled ? 'bg-primary shadow-[0_0_8px_var(--primary)]' : 'bg-muted-foreground'}`} />
                        </button>
                      </div>
                      <div className="text-sm text-muted-foreground mb-4 min-h-[40px]">
                        {cmd.description}
                      </div>
                      <div className="flex justify-between items-center text-xs font-mono border-t border-border pt-3">
                        <span className="text-primary/70">REQ: {cmd.permissions}</span>
                        <span className="text-muted-foreground">USED: {formatNumber(cmd.usageCount)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </Layout>
    </RequireAuth>
  );
}
