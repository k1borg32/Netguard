import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { App } from './App'
import { AuthProvider } from './auth/AuthProvider'
import { isRetryable } from './lib/errors'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Network errors, 5xx and 429 (rate limiting) get two more tries with a growing delay; other 4xx won't get better.
      retry: (failureCount, error) => failureCount < 2 && isRetryable(error),
      refetchOnWindowFocus: true,
    },
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <App />
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
