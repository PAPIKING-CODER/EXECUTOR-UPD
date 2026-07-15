import { RequireAuth } from '@/hooks/use-auth';
import { Layout } from '@/components/layout';
import { useListBlacklist, useAddBlacklist, useRemoveBlacklist, BlacklistEntryInputType, ListBlacklistType } from '@workspace/api-client-react';
import { useState } from 'react';
import { Plus, Trash2, ShieldBan } from 'lucide-react';

export default function Blacklist() {
  const [activeTab, setActiveTab] = useState<ListBlacklistType>('user');
  const { data, refetch } = useListBlacklist({ type: activeTab });
  const addBlacklist = useAddBlacklist();
  const removeBlacklist = useRemoveBlacklist();

  const [newId, setNewId] = useState('');
  const [newReason, setNewReason] = useState('');

  const handleAdd = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newId) return;
    addBlacklist.mutate({
      data: {
        type: activeTab as BlacklistEntryInputType,
        targetId: newId,
        reason: newReason || undefined
      }
    }, {
      onSuccess: () => {
        setNewId('');
        setNewReason('');
        refetch();
      }
    });
  };

  const handleRemove = (id: number) => {
    if (!window.confirm("Remove from blacklist?")) return;
    removeBlacklist.mutate({ id }, {
      onSuccess: () => refetch()
    });
  };

  return (
    <RequireAuth>
      <Layout>
        <div className="p-8 space-y-6 max-w-[1200px] mx-auto">
          <header className="flex items-center gap-3">
            <ShieldBan className="w-8 h-8 text-destructive" />
            <h1 className="text-2xl font-bold tracking-widest text-foreground uppercase">Threat Quarantine</h1>
          </header>

          <div className="flex space-x-1 border-b border-border">
            {(['user', 'server', 'word'] as ListBlacklistType[]).map(tab => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-6 py-3 font-mono text-sm tracking-widest uppercase transition-colors ${
                  activeTab === tab 
                  ? 'bg-destructive/10 text-destructive border-t border-l border-r border-destructive/30' 
                  : 'text-muted-foreground hover:text-foreground hover:bg-white/5'
                }`}
              >
                {tab}s
              </button>
            ))}
          </div>

          <form onSubmit={handleAdd} className="glass-panel p-6 flex gap-4 items-end bg-destructive/5 border-destructive/20">
            <div className="flex-1 space-y-2">
              <label className="text-xs font-mono text-destructive uppercase tracking-widest">Target ID / Word</label>
              <input 
                value={newId}
                onChange={e => setNewId(e.target.value)}
                className="w-full bg-black border border-destructive/30 text-foreground font-mono px-4 py-2 focus:outline-none focus:border-destructive placeholder:text-muted-foreground/50"
                placeholder="ENTER_IDENTIFIER..."
              />
            </div>
            <div className="flex-2 space-y-2 w-1/2">
              <label className="text-xs font-mono text-destructive uppercase tracking-widest">Reason (Optional)</label>
              <input 
                value={newReason}
                onChange={e => setNewReason(e.target.value)}
                className="w-full bg-black border border-destructive/30 text-foreground font-mono px-4 py-2 focus:outline-none focus:border-destructive placeholder:text-muted-foreground/50"
                placeholder="VIOLATION_DETAILS..."
              />
            </div>
            <button 
              type="submit"
              className="bg-destructive/20 hover:bg-destructive/40 text-destructive border border-destructive/50 px-6 py-2 font-mono uppercase tracking-widest transition-all h-[42px] flex items-center gap-2"
              disabled={!newId}
            >
              <Plus className="w-4 h-4" /> Add
            </button>
          </form>

          <div className="glass-panel border-destructive/20">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-black/60 border-b border-destructive/20 text-xs font-mono tracking-widest text-destructive uppercase">
                  <th className="p-4 font-normal">Target ID</th>
                  <th className="p-4 font-normal">Target Name</th>
                  <th className="p-4 font-normal">Reason</th>
                  <th className="p-4 font-normal">Added By</th>
                  <th className="p-4 font-normal">Date</th>
                  <th className="p-4 font-normal text-center">Action</th>
                </tr>
              </thead>
              <tbody className="font-mono text-sm">
                {data?.entries.map((entry) => (
                  <tr key={entry.id} className="border-b border-white/5 hover:bg-white/5 transition-colors group">
                    <td className="p-4 text-foreground">{entry.targetId}</td>
                    <td className="p-4 text-muted-foreground">{entry.targetName || '-'}</td>
                    <td className="p-4 text-muted-foreground">{entry.reason || 'No reason provided'}</td>
                    <td className="p-4 text-muted-foreground text-xs">{entry.addedBy}</td>
                    <td className="p-4 text-muted-foreground">{new Date(entry.addedAt).toLocaleDateString()}</td>
                    <td className="p-4 text-center">
                      <button 
                        onClick={() => handleRemove(entry.id)}
                        className="p-2 text-destructive hover:bg-destructive/10 border border-transparent hover:border-destructive/30 transition-all opacity-0 group-hover:opacity-100"
                        title="Remove"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
                {data?.entries.length === 0 && (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-muted-foreground font-mono">
                      NO_ACTIVE_THREATS
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </Layout>
    </RequireAuth>
  );
}
