import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { Route, Switch, Router as WouterRouter } from 'wouter';
import { AuthProvider } from '@/hooks/use-auth';

import Login from '@/pages/login';
import Dashboard from '@/pages/dashboard';
import Servers from '@/pages/servers';
import Blacklist from '@/pages/blacklist';
import Logs from '@/pages/logs';
import Commands from '@/pages/commands';
import Stats from '@/pages/stats';
import Settings from '@/pages/settings';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

function NotFound() {
  return (
    <div className="min-h-screen bg-background flex items-center justify-center font-mono text-destructive">
      [ 404_NOT_FOUND ]
    </div>
  );
}

function Router() {
  return (
    <Switch>
      <Route path="/" component={Login} />
      <Route path="/dashboard" component={Dashboard} />
      <Route path="/servers" component={Servers} />
      <Route path="/blacklist" component={Blacklist} />
      <Route path="/logs" component={Logs} />
      <Route path="/commands" component={Commands} />
      <Route path="/stats" component={Stats} />
      <Route path="/settings" component={Settings} />
      <Route component={NotFound} />
    </Switch>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <WouterRouter base={import.meta.env.BASE_URL.replace(/\/$/, '')}>
        <AuthProvider>
          <Router />
        </AuthProvider>
      </WouterRouter>
      <Toaster theme="dark" />
    </QueryClientProvider>
  );
}

export default App;
