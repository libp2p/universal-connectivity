import React, { createContext, useContext, useState } from 'react';

export interface ChatFile {
  id: string
  body: Uint8Array
  sender: string
}

export interface FileChatContextInterface {
  files: Map<string, ChatFile>
  setFiles: (files: Map<string, ChatFile>) => void;
}
export const fileContext = createContext<FileChatContextInterface>({
  files: new Map<string, ChatFile>(),
  setFiles: () => { }
})

export const useFileChatContext = () => {
  return useContext(fileContext);
};

export const FileProvider = ({ children }: any) => {
  const [files, setFiles] = useState<Map<string, ChatFile>>(new Map<string, ChatFile>());

  return (
    <fileContext.Provider value={{ files, setFiles }}>
      {children}
    </fileContext.Provider>
  );
};
