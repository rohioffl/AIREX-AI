import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate, Link, useSearchParams } from 'react-router-dom'
import { Shield, Mail, Lock, Eye, EyeOff, User, ArrowRight, Loader, CheckCircle2, Activity, Zap } from 'lucide-react'
import { useAuth } from '../context/AuthContext'
import { register } from '../services/auth'
import { extractErrorMessage } from '../utils/errorHandler'
import landFinalBg from '../assets/land_final.jpg'

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID || '671714206735-8tdd47qt6el9m33fs4kjnocjqrcsq9dg.apps.googleusercontent.com'

export default function LoginPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { login, loginWithGoogle } = useAuth()
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const googleButtonRef = useRef(null)
  
  // Rotating status messages
  const [statusIndex, setStatusIndex] = useState(0)
  const statuses = [
    { icon: Activity, text: "System Operational", sub: "All services running normal" },
    { icon: Shield, text: "Security Active", sub: "Threat detection enabled" },
    { icon: Zap, text: "AI Analysis Ready", sub: "Neural engine standby" }
  ]
  const acceptInvitationToken = searchParams.get('accept_invitation_token')

  const getPostLoginPath = useCallback(() => {
    if (acceptInvitationToken) {
      return `/accept-invitation?token=${encodeURIComponent(acceptInvitationToken)}`
    }
    return '/dashboard'
  }, [acceptInvitationToken])

  useEffect(() => {
    const interval = setInterval(() => {
      setStatusIndex(prev => (prev + 1) % statuses.length)
    }, 4000)
    return () => clearInterval(interval)
  }, [statuses.length])

  const handleGoogleResponse = useCallback(async (response) => {
    setLoading(true)
    setError(null)
    try {
      await loginWithGoogle(response.credential)
      navigate(getPostLoginPath(), { replace: true })
    } catch (err) {
      setError(extractErrorMessage(err) || 'Google sign-in failed')
    } finally {
      setLoading(false)
    }
  }, [getPostLoginPath, loginWithGoogle, navigate])

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return

    const initGoogle = () => {
      if (!window.google?.accounts?.id) return
      window.google.accounts.id.initialize({
        client_id: GOOGLE_CLIENT_ID,
        callback: handleGoogleResponse,
      })
      if (googleButtonRef.current) {
        googleButtonRef.current.innerHTML = ''
        window.google.accounts.id.renderButton(googleButtonRef.current, {
          type: 'standard',
          theme: 'outline',
          size: 'large',
          text: 'continue_with',
          shape: 'pill',
          width: 340,
        })
      }
    }

    if (window.google?.accounts?.id) {
      initGoogle()
      return undefined
    }

    const script = document.createElement('script')
    script.src = 'https://accounts.google.com/gsi/client'
    script.async = true
    script.defer = true
    script.onload = initGoogle
    document.head.appendChild(script)

    return () => {
      if (document.head.contains(script)) document.head.removeChild(script)
    }
  }, [handleGoogleResponse])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      if (mode === 'register') {
        await register({ email, password, displayName })
        setMode('login')
        setError(null)
      }
      if (mode === 'login' || mode !== 'register') {
        await login({ email, password })
        navigate(getPostLoginPath(), { replace: true })
      }
    } catch (err) {
      const msg = extractErrorMessage(err) || err.message || 'Something went wrong'
      setError(msg)
    } finally {
      setLoading(false)
    }
  }

  const switchMode = () => {
    setMode(m => m === 'login' ? 'register' : 'login')
    setError(null)
  }

  const CurrentStatusIcon = statuses[statusIndex].icon

  return (
    <div className="min-h-screen flex items-center justify-center font-sans text-slate-200 bg-[#020617] relative overflow-hidden p-6">
      
      {/* ── Cinematic Animated Background ── */}
      <div className="absolute inset-0 z-0 overflow-hidden bg-black">
        <div 
          className="absolute inset-0 bg-cover bg-center animate-ken-burns opacity-70"
          style={{ backgroundImage: `url(${landFinalBg})` }}
        />
        <div className="absolute inset-0 bg-gradient-to-tr from-black via-black/40 to-blue-900/20 mix-blend-multiply" />
        <div className="absolute inset-0 bg-[url('/noise.svg')] opacity-20 mix-blend-overlay" aria-hidden />
      </div>

      {/* ── Main Interface ── */}
      <div className="relative z-10 w-full max-w-[1200px]">
        
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 lg:gap-4 items-center">
          
          {/* ── Left Column: Brand & Status ── */}
          <div className="lg:col-span-3 flex flex-col items-center lg:items-start gap-8 order-2 lg:order-1 animate-fade-in-up" style={{ animationDelay: '0s' }}>
            {/* Brand Logo */}
            <div className="text-center lg:text-left">
              <Link to="/" className="inline-flex items-center gap-3 group">
                <div className="w-12 h-12 rounded-2xl bg-white/10 backdrop-blur-md border border-white/10 flex items-center justify-center shadow-lg group-hover:bg-white/20 transition-all duration-300 ring-1 ring-white/10">
                  <Shield size={24} className="text-white" strokeWidth={2.5} />
                </div>
                <span className="text-2xl font-black tracking-tighter text-white drop-shadow-md">AIREX</span>
              </Link>
            </div>

            {/* System Status Indicator */}
            <div className="bg-white/[0.03] backdrop-blur-xl border border-white/10 rounded-2xl p-5 flex flex-col gap-4 shadow-xl ring-1 ring-white/10 w-full max-w-[240px] animate-pulse-slow">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-indigo-600 flex items-center justify-center text-white shadow-lg">
                  <CurrentStatusIcon size={20} />
                </div>
                <div>
                  <div className="text-[10px] text-blue-200/60 font-bold uppercase tracking-widest leading-none mb-1.5">
                    Live Status
                  </div>
                  <div className="text-sm font-bold text-white tracking-wide leading-none">
                    {statuses[statusIndex].text}
                  </div>
                </div>
              </div>
              <div className="space-y-2 pt-2 border-t border-white/5">
                <div className="flex justify-between items-center">
                  <span className="text-[10px] text-slate-500 uppercase font-bold">Network</span>
                  <span className="text-[10px] text-green-400 font-mono">99.9%</span>
                </div>
                <div className="w-full h-1 bg-white/5 rounded-full overflow-hidden">
                  <div className="h-full bg-blue-500 w-[99%]" />
                </div>
              </div>
            </div>
          </div>

          {/* ── Center Column: The Login Box ── */}
          <div className="lg:col-span-6 flex justify-center order-1 lg:order-2 animate-fade-in-up" style={{ animationDelay: '0.15s' }}>
            {/* Crystal Clear Transparent Box */}
            <div className="bg-gradient-to-br from-slate-900/40 via-slate-800/30 to-slate-900/40 backdrop-blur-2xl border border-white/20 rounded-[2.5rem] p-8 lg:p-12 shadow-[0_32px_64px_-16px_rgba(0,0,0,0.8)] ring-1 ring-white/20 relative overflow-hidden w-full max-w-[460px]">
              {/* Subtle Inner Glow */}
              <div className="absolute -top-24 -left-24 w-48 h-48 bg-blue-500/15 blur-[60px] rounded-full pointer-events-none" />
              {/* Additional gradient overlay for depth */}
              <div className="absolute inset-0 bg-gradient-to-br from-blue-500/5 via-transparent to-purple-500/5 pointer-events-none rounded-[2.5rem]" />
              
              {/* Processing Overlay */}
              {loading && (
                <div className="absolute inset-0 z-20 bg-slate-950/40 backdrop-blur-[2px] flex items-center justify-center animate-pulse">
                  <div className="flex flex-col items-center gap-3">
                    <Loader size={32} className="animate-spin text-blue-400" />
                    <span className="text-[10px] font-bold text-blue-400 uppercase tracking-[0.3em] ml-1">Authenticating</span>
                  </div>
                </div>
              )}
              
              <div className={`relative z-10 transition-opacity duration-300 ${loading ? 'opacity-30 pointer-events-none' : 'opacity-100'}`}>
                <div className="mb-8">
                  <h1 className="text-3xl font-bold text-white tracking-tight mb-2">
                    {mode === 'login' ? 'Authorize' : 'Join Unit'}
                  </h1>
                  <p className="text-slate-400 text-sm font-medium">
                    {mode === 'login' ? 'Secure session gateway.' : 'Deploy new operator account.'}
                  </p>
                </div>

                {error && (
                  <div className="mb-6 p-4 rounded-2xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm font-medium flex items-center gap-3 animate-shake">
                    <div className="w-1.5 h-1.5 rounded-full bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.8)]" />
                    {error}
                  </div>
                )}

                <form onSubmit={handleSubmit} className="space-y-6">
                  {mode === 'register' && (
                    <div className="space-y-2">
                      <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-[0.15em] ml-1">
                        Identity Name
                      </label>
                      <div className="relative group">
                        <User size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 group-focus-within:text-blue-400 transition-colors duration-200" />
                        <input
                          type="text"
                          value={displayName}
                          onChange={(e) => setDisplayName(e.target.value)}
                          placeholder="OPERATOR_ID"
                          required
                          className="w-full bg-black/40 hover:bg-black/50 focus:bg-black/50 border border-white/5 focus:border-blue-500/50 rounded-2xl py-3.5 pl-12 pr-4 text-white placeholder-slate-600 outline-none transition-all duration-300 focus:shadow-[0_0_30px_rgba(59,130,246,0.15)]"
                        />
                      </div>
                    </div>
                  )}

                  <div className="space-y-2">
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-[0.15em] ml-1">
                      Email
                    </label>
                    <div className="relative group">
                      <Mail size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-blue-400 transition-colors duration-200" />
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder=""
                        required
                        autoComplete="email"
                        className="w-full bg-black/40 hover:bg-black/50 focus:bg-black/50 border border-white/5 focus:border-blue-500/50 rounded-2xl py-3.5 pl-12 pr-4 text-white placeholder-slate-600 outline-none transition-all duration-300 focus:shadow-[0_0_30px_rgba(59,130,246,0.15)]"
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-[0.15em] ml-1">
                      Password
                    </label>
                    <div className="relative group">
                      <Lock size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500 group-focus-within:text-blue-400 transition-colors duration-200" />
                      <input
                        type={showPassword ? 'text' : 'password'}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••••••"
                        required
                        minLength={6}
                        autoComplete="current-password"
                        className="w-full bg-black/40 hover:bg-black/50 focus:bg-black/50 border border-white/5 focus:border-blue-500/50 rounded-2xl py-3.5 pl-12 pr-12 text-white placeholder-slate-600 outline-none transition-all duration-300 focus:shadow-[0_0_30px_rgba(59,130,246,0.15)]"
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(v => !v)}
                        className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition-colors p-1.5 rounded-xl hover:bg-white/5"
                      >
                        {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                      </button>
                    </div>
                  </div>

                  <button
                    type="submit"
                    disabled={loading}
                    className="w-full bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-bold py-4 rounded-2xl transition-all duration-300 flex items-center justify-center gap-3 shadow-xl shadow-blue-600/20 hover:shadow-blue-600/40 hover:-translate-y-1 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:translate-y-0 mt-4 group"
                  >
                    {loading ? (
                      <Loader size={20} className="animate-spin" />
                    ) : (
                      <>
                        <span className="tracking-widest uppercase text-xs">{mode === 'login' ? 'Authorize Session' : 'Register Unit'}</span>
                        <ArrowRight size={18} className="group-hover:translate-x-1 transition-transform" />
                      </>
                    )}
                  </button>
                </form>

                {GOOGLE_CLIENT_ID && mode === 'login' && (
                  <div className="mt-4">
                    <div className="flex items-center gap-3 my-4">
                      <div className="flex-1 h-px bg-white/10" />
                      <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">or</span>
                      <div className="flex-1 h-px bg-white/10" />
                    </div>
                    <div className="w-full rounded-2xl bg-white p-1 min-h-[46px] flex items-center justify-center" ref={googleButtonRef} />
                  </div>
                )}

                <div className="mt-10 pt-6 border-t border-white/5 text-center">
                  <p className="text-slate-400 text-[13px] font-medium tracking-wide">
                    {mode === 'login' ? "New operator?" : "Already verified?"}
                    <button
                      onClick={switchMode}
                      className="ml-2 text-blue-400 hover:text-blue-300 font-bold transition-colors hover:underline decoration-blue-400/30 underline-offset-4"
                    >
                      {mode === 'login' ? 'Request Access' : 'Return to Login'}
                    </button>
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* ── Right Column: Testimonial ── */}
          <div className="lg:col-span-3 flex flex-col gap-6 order-3 animate-fade-in-up" style={{ animationDelay: '0.3s' }}>
            <div className="bg-white/[0.03] backdrop-blur-xl border border-white/10 rounded-2xl p-6 shadow-xl ring-1 ring-white/10">
              <div className="flex gap-1 mb-4">
                {[...Array(5)].map((_, i) => (
                  <CheckCircle2 key={i} size={12} className="text-blue-500" fill="currentColor" fillOpacity={0.2} />
                ))}
              </div>
              <blockquote className="text-sm font-medium text-slate-300 leading-relaxed italic">
                "AIREX has redefined our SRE workflow. Immediate ROI and seamless execution."
              </blockquote>
              <div className="mt-4 flex items-center gap-3">
                <div className="w-8 h-8 rounded-full bg-blue-500/20 flex items-center justify-center text-[10px] font-bold text-blue-400">
                  PE
                </div>
                <div className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">
                  Platform Engineer
                </div>
              </div>
            </div>

            {/* Micro Stats */}
            <div className="px-6 space-y-3">
              <div className="flex justify-between text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                <span>Avg MTTR</span>
                <span className="text-white font-mono">-85%</span>
              </div>
              <div className="flex justify-between text-[10px] font-bold text-slate-400 uppercase tracking-widest">
                <span>Deployment</span>
                <span className="text-white font-mono">Global</span>
              </div>
            </div>
          </div>

        </div>

      </div>

      <style>{`
        @keyframes fade-in-up {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        .animate-fade-in-up {
          animation: fade-in-up 0.8s cubic-bezier(0.16, 1, 0.3, 1) forwards;
        }
        
        @keyframes shake {
          0%, 100% { transform: translateX(0); }
          25% { transform: translateX(-4px); }
          75% { transform: translateX(4px); }
        }
        .animate-shake {
          animation: shake 0.4s cubic-bezier(0.36, 0.07, 0.19, 0.97) both;
        }

        /* Cinematic Background Movement */
        @keyframes ken-burns {
          0% { transform: scale(1) translate(0, 0); }
          50% { transform: scale(1.1) translate(-1%, -1%); }
          100% { transform: scale(1) translate(0, 0); }
        }
        .animate-ken-burns {
          animation: ken-burns 40s ease-in-out infinite;
        }

        @keyframes pulse-slow {
          0%, 100% { opacity: 0.8; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.02); }
        }
        .animate-pulse-slow {
          animation: pulse-slow 4s ease-in-out infinite;
        }
      `}</style>
    </div>
  )
}
