import { useEffect } from 'react';
import { useAuth } from '@/hooks/use-auth';
import { useLocation } from 'wouter';
import { Terminal } from 'lucide-react';
import { motion } from 'framer-motion';

export default function Login() {
  const { isAuthenticated, isLoading } = useAuth();
  const [, setLocation] = useLocation();

  useEffect(() => {
    if (!isLoading && isAuthenticated) {
      setLocation('/dashboard');
    }
  }, [isLoading, isAuthenticated, setLocation]);

  const handleLogin = () => {
    window.location.href = '/api/auth/discord';
  };

  if (isLoading) return null;

  return (
    <div className="min-h-[100dvh] flex items-center justify-center bg-background relative overflow-hidden">
      <div className="scanline" />
      
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgba(0,255,136,0.05),transparent_50%)]" />

      <motion.div 
        initial={{ opacity: 0, scale: 0.95 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.5, ease: "easeOut" }}
        className="relative z-10 glass-panel p-10 max-w-md w-full border border-primary/20 glow-border"
      >
        <div className="flex flex-col items-center text-center space-y-6">
          <div className="w-20 h-20 rounded-none border border-primary/50 bg-black/50 flex items-center justify-center glow-border relative">
            <div className="absolute inset-0 border-[0.5px] border-primary/30 m-1" />
            <Terminal className="w-10 h-10 text-primary" />
          </div>
          
          <div className="space-y-2">
            <h1 className="text-3xl font-bold tracking-widest text-foreground uppercase glitch-hover">
              FMD <span className="text-primary">BOT</span>
            </h1>
            <p className="text-sm font-mono text-primary/70 tracking-widest uppercase">
              Owner Access Only
            </p>
          </div>

          <div className="w-full h-px bg-gradient-to-r from-transparent via-primary/50 to-transparent my-4" />

          <button 
            onClick={handleLogin}
            className="w-full bg-primary/10 hover:bg-primary/20 border border-primary text-primary font-mono py-4 px-6 uppercase tracking-widest transition-all hover:shadow-[0_0_20px_rgba(0,255,136,0.3)] active:scale-[0.98] flex items-center justify-center gap-3 group"
          >
            <span>Initiate Handshake</span>
            <span className="opacity-0 group-hover:opacity-100 transition-opacity animate-pulse">_</span>
          </button>
        </div>
      </motion.div>
    </div>
  );
}
