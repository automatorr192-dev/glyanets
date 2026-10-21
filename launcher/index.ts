// Пока сервер не запущен, бот только открывает мини-апп: на любое сообщение отвечает
// приветствием и кнопкой. Каждый запрос несёт секрет из setWebhook, чужие отклоняются.

interface Env {
  BOT_TOKEN: string;
  WEBHOOK_SECRET: string;
  WEBAPP_URL: string;
}

const WELCOME = "Здравствуйте! Записаться можно кнопкой ниже: услуги, время и итоговая цена — в приложении.";
const BUTTON = "Записаться";

export default {
  async fetch(request: Request, env: Env) {
    if (
      request.method !== "POST" ||
      request.headers.get("X-Telegram-Bot-Api-Secret-Token") !== env.WEBHOOK_SECRET
    ) {
      return new Response("Not found", { status: 404 });
    }
    const update: { message?: { chat: { id: number } } } = await request.json();
    if (update.message) {
      await fetch(`https://api.telegram.org/bot${env.BOT_TOKEN}/sendMessage`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          chat_id: update.message.chat.id,
          text: WELCOME,
          parse_mode: "HTML",
          reply_markup: { inline_keyboard: [[{ text: BUTTON, web_app: { url: env.WEBAPP_URL } }]] },
        }),
      });
    }
    return new Response("ok");
  },
};
