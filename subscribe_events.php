<?php
/**
 * Скрипт для подписки на события Bitrix24
 * Запустите этот скрипт один раз для настройки подписки
 */

// Конфигурация
$webhook_url = 'http://bookntrack.online:8081/webhook_tasks';
$auth_token = 'gu3ckdtubvwpbnru6418p8wbdv1khsqq';
$bitrix24_domain = 'intranet.vedagent.ru';

// Формируем полный endpoint для вызова event.bind
$rest_endpoint = 'https://' . $bitrix24_domain . '/rest/event.bind.json';

// Функция для отправки запроса
function sendRequest($url, $data) {
    $ch = curl_init($url . '?' . http_build_query($data));
    curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
    curl_setopt($ch, CURLOPT_SSL_VERIFYPEER, false);
    $result = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);
    return [
        'code' => $httpCode,
        'data' => json_decode($result, true)
    ];
}

echo "=== Подписка на события Bitrix24 ===\n\n";
echo "Webhook URL: $webhook_url\n";
echo "Bitrix24 Domain: $bitrix24_domain\n\n";

// Данные для подписки на OnTaskAdd
$eventDataAdd = [
    'auth' => $auth_token,
    'event' => 'OnTaskAdd',
    'handler' => $webhook_url
];

// Данные для подписки на OnTaskUpdate
$eventDataUpdate = [
    'auth' => $auth_token,
    'event' => 'OnTaskUpdate',
    'handler' => $webhook_url
];

// Выполняем подписку на OnTaskAdd
echo "Подписка на OnTaskAdd...\n";
$resultAdd = sendRequest($rest_endpoint, $eventDataAdd);
if ($resultAdd['code'] == 200 && isset($resultAdd['data']['result'])) {
    echo "✅ Успешно подписан на OnTaskAdd\n";
    print_r($resultAdd['data']);
} else {
    echo "❌ Ошибка подписки на OnTaskAdd:\n";
    print_r($resultAdd);
}

echo "\n";

// Выполняем подписку на OnTaskUpdate
echo "Подписка на OnTaskUpdate...\n";
$resultUpdate = sendRequest($rest_endpoint, $eventDataUpdate);
if ($resultUpdate['code'] == 200 && isset($resultUpdate['data']['result'])) {
    echo "✅ Успешно подписан на OnTaskUpdate\n";
    print_r($resultUpdate['data']);
} else {
    echo "❌ Ошибка подписки на OnTaskUpdate:\n";
    print_r($resultUpdate);
}

echo "\n=== Готово! ===\n";
echo "Теперь Bitrix24 будет отправлять события на: $webhook_url\n";
?>

