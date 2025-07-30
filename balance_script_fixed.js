function updateBalance() {
  const sheetName = 'Баланс';
  let sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(sheetName);
  
  if (!sheet) {
    sheet = SpreadsheetApp.getActiveSpreadsheet().insertSheet(sheetName);
    sheet.getRange('A1:D1').setValues([['Дата', 'Сумма', 'Описание', 'Текущий баланс']]);
  }

  try {
    const response = UrlFetchApp.fetch('http://165.232.145.149:8002/balance-history', {
      headers: {
        'Authorization': 'Bearer RfgLep4Y7nWjXky5qA0lpwV2E6kyZiOBkrKrHo7cl3k'
      }
    });
    
    const data = JSON.parse(response.getContentText());
    const balanceHistory = data.balance_history;

    // Очищаем лист кроме заголовков
    sheet.getRange('A2:D').clear();

    if (balanceHistory.length === 0) {
      return;
    }

    // Сортируем данные по timestamp в хронологическом порядке (старые сначала)
    const sortedHistory = balanceHistory.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    // Создаем массив для накопительного баланса в хронологическом порядке
    const balanceCalculations = [];
    let runningBalance = 0;

    // Вычисляем накопительный баланс
    for (const item of sortedHistory) {
      runningBalance += item.amount;
      balanceCalculations.push({
        timestamp: item.timestamp,
        amount: item.amount,
        description: item.description,
        balance: runningBalance
      });
    }

    // Теперь переворачиваем для отображения (новые сверху)
    const reversedData = balanceCalculations.reverse();

    // Подготавливаем данные для записи
    const dataToWrite = reversedData.map(item => [
      item.timestamp,
      item.amount,
      item.description,
      item.balance
    ]);

    if (dataToWrite.length > 0) {
      sheet.getRange(2, 1, dataToWrite.length, 4).setValues(dataToWrite);
    }

    // Финальный баланс (последняя операция в хронологическом порядке)
    const finalBalance = balanceCalculations[balanceCalculations.length - 1]?.balance || 0;
    console.log(`Обновлено ${dataToWrite.length} записей. Текущий баланс: ${finalBalance}`);
    
  } catch (error) {
    console.error('Ошибка при обновлении баланса:', error);
  }
}