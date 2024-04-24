import { DirectMessagesList } from "@/components/directmessages/DirectMessagesList";
import { Rooms } from "@/components/Rooms";

export const LeftSidebar = () => {
  return (
    <>
      <Rooms />
      <DirectMessagesList />
    </>
  );
};
