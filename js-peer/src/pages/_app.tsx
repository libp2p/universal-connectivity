import type { AppProps } from 'next/app'
import { ToastContainer } from 'react-toastify'
import { BackgroundComponents } from '@/components/BackgroundComponents'
import { AppWrapper } from '@/context/ctx'

import '@/styles/globals.css'
import 'react-toastify/dist/ReactToastify.css'

export default function App({ Component, pageProps }: AppProps) {
  return (
    <AppWrapper>
      <Component {...pageProps} />
      <BackgroundComponents />
      <ToastContainer
        position="bottom-right"
        autoClose={2000}
        hideProgressBar
        newestOnTop
        closeOnClick
        rtl={false}
        pauseOnFocusLoss
        draggable={false}
        pauseOnHover
        theme="colored"
      />
    </AppWrapper>
  )
}
