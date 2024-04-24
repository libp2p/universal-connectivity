import { useChatContext } from "@/context/chat-ctx";

export const Rooms = () => {
  const { setChatRoom } = useChatContext();
  const handleRoomChange = () => {
    setChatRoom("");
  };

  return (
    <>
      <h1 className="font-bold text-gray-600">Rooms</h1>
      <span className="cursor-pointer" onClick={handleRoomChange}>
        Public
      </span>
    </>
  );
};
