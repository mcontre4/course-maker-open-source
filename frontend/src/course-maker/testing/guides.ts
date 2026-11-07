import type {
  GuideChat,
  GuideMemory,
  GuideRole,
  Guides,
  OutlineVersion,
} from "../application/guides";

export class MemoryGuides implements Guides {
  chats: GuideChat[] = [];
  savedMemories: GuideMemory[] = [];
  savedVersions: OutlineVersion[] = [];
  requests: Parameters<Guides["send"]>[0][] = [];
  loseNextResponse = false;
  private receipts = new Map<string, GuideChat>();

  async list(resourceId: string, guide: GuideRole) {
    return this.chats.filter(
      (chat) => chat.resourceId === resourceId && chat.guide === guide,
    );
  }
  async create(resourceId: string, guide: GuideRole, title: string) {
    const chat: GuideChat = {
      id: "chat_" + (this.chats.length + 1),
      resourceId,
      guide,
      title,
      revision: 0,
      turns: [],
      hasMore: false,
    };
    this.chats.push(chat);
    return chat;
  }
  async get(id: string, before?: number) {
    const chat = this.chats.find((item) => item.id === id);
    if (!chat) throw new Error("Chat not found");
    const turns = chat.turns.filter(
      (turn) => before === undefined || turn.revision < before,
    );
    return { ...chat, turns: turns.slice(-100), hasMore: turns.length > 100 };
  }
  async send(request: Parameters<Guides["send"]>[0]) {
    this.requests.push(request);
    const receipt = this.receipts.get(request.requestId);
    if (receipt) return receipt;
    const index = this.chats.findIndex((chat) => chat.id === request.threadId);
    const old = this.chats[index];
    if (old.revision !== request.expectedRevision)
      throw new Error("Chat changed");
    const chat = {
      ...old,
      revision: old.revision + 1,
      turns: [
        ...old.turns,
        {
          id: "message_" + (old.revision + 1),
          revision: old.revision + 1,
          user: request.message,
          assistant: "I remember our conversation: " + request.message,
        },
      ],
    };
    this.chats[index] = chat;
    this.receipts.set(request.requestId, chat);
    if (this.loseNextResponse) {
      this.loseNextResponse = false;
      throw new Error("Connection interrupted. Retry your message.");
    }
    return chat;
  }
  async memories() {
    return this.savedMemories;
  }
  async changeMemory(
    _resourceId: string,
    memory: GuideMemory,
    content: string | null,
  ) {
    this.savedMemories =
      content === null
        ? this.savedMemories.filter((item) => item.id !== memory.id)
        : this.savedMemories.map((item) =>
            item.id === memory.id
              ? { ...item, content, revision: item.revision + 1 }
              : item,
          );
  }
  async versions() {
    return this.savedVersions;
  }
}
