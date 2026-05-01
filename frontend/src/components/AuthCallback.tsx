import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { authService } from '../services/auth';
import type { User } from '../types';

function AuthCallback() {
  const [status, setStatus] = useState<'loading' | 'success' | 'error'>('loading');
  const [message, setMessage] = useState('');
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  useEffect(() => {
    const handleCallback = async () => {
      try {
        const accessToken = searchParams.get('access_token');
        const tokenType = searchParams.get('token_type');
        const userParam = searchParams.get('user');

        if (accessToken && tokenType && userParam) {
          const parsedUser = JSON.parse(userParam) as User;
          authService.setAuthData({
            access_token: accessToken,
            token_type: tokenType,
            user: parsedUser,
          });

          setStatus('success');
          setMessage('Login successful! Redirecting...');
          setTimeout(() => {
            window.location.href = '/';
          }, 700);
          return;
        }

        const code = searchParams.get('code');
        if (!code) {
          throw new Error('No authorization code received');
        }

        const authData = await authService.handleGoogleCallback(code);
        authService.setAuthData(authData);

        setStatus('success');
        setMessage('Login successful! Redirecting...');

        // Redirect to main app after a short delay
        setTimeout(() => {
          window.location.href = '/';
        }, 1000);

      } catch (error) {
        setStatus('error');
        if (axios.isAxiosError(error)) {
          const detail = error.response?.data?.detail;
          setMessage(typeof detail === 'string' ? detail : 'Login failed');
        } else {
          setMessage(error instanceof Error ? error.message : 'Login failed');
        }
      }
    };

    handleCallback();
  }, [searchParams, navigate]);

  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center">
      <div className="max-w-md w-full bg-white rounded-3xl shadow-sm p-8">
        <div className="text-center">
          {status === 'loading' && (
            <>
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
              <h2 className="text-xl font-semibold text-slate-900 mb-2">Completing Login</h2>
              <p className="text-slate-600">Please wait while we authenticate you...</p>
            </>
          )}

          {status === 'success' && (
            <>
              <div className="w-12 h-12 bg-green-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-slate-900 mb-2">Login Successful!</h2>
              <p className="text-slate-600">{message}</p>
            </>
          )}

          {status === 'error' && (
            <>
              <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center mx-auto mb-4">
                <svg className="w-6 h-6 text-red-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-slate-900 mb-2">Login Failed</h2>
              <p className="text-red-600 mb-4">{message}</p>
              <button
                onClick={() => navigate('/login')}
                className="bg-blue-600 hover:bg-blue-700 text-white font-semibold py-2 px-4 rounded-2xl transition"
              >
                Try Again
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

export default AuthCallback;