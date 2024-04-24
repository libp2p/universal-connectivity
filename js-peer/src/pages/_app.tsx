import type { AppProps } from "next/app";
import { BackgroundComponents } from "@/components/BackgroundComponents";
import { AppWrapper } from "@/context/ctx";
import "@/styles/globals.css";

export default function App({ Component, pageProps }: AppProps) {
  return (
    <AppWrapper>
      <Component {...pageProps} />
      <BackgroundComponents />
    </AppWrapper>
  );
}
