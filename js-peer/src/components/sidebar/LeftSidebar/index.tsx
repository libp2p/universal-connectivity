import { Rooms } from "@/components/Rooms"
import { DirectMessagesList } from "@/components/directmessages/DirectMessagesList"

export const LeftSidebar = () => {
  return (
    <>
      <Rooms />
      <DirectMessagesList />
    </>
  )
}
