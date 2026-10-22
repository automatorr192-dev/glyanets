// Бесплатный Render усыпляет сервер Глянца через 15 минут без запросов, а напоминания о
// визите шлёт его фоновая проверка. Днём будим его раз в 10 минут: ночью записей нет,
// а часы бесплатного Render на аккаунт ограничены.

interface Env {
  SERVER_URL: string;
}

export default {
  async scheduled(_controller: ScheduledController, env: Env) {
    const response = await fetch(`${env.SERVER_URL}/health`);
    console.log(`Глянец ответил ${response.status}`);
  },
};
