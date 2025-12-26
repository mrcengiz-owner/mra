# NexKasa API Entegrasyon Rehberi

## 1. Giriş
Bu doküman, **NexKasa** ödeme sistemine entegrasyon sağlamak isteyen iş ortakları (Merchant/Client) için hazırlanmıştır. Sistem, güvenli **API Key** tabanlı otantikasyon kullanır ve RESTful mimariye sahiptir.

---

## 2. Otantikasyon (Authentication)
Tüm API isteklerinde `X-API-KEY` başlığı (header) zorunludur.

*   **Header Key:** `X-API-KEY`
*   **Value:** Size özel üretilen API Anahtarı (Admin panelinden temin edilmelidir).

**Örnek Header:**
```http
Content-Type: application/json
X-API-KEY: 12345678-abcd-1234-abcd-1234567890ab
```

---

## 3. Endpoints (Uç Noktalar)
**Base URL (Canlı):** `https://nexkasa.com` (veya tanımlı domain)

### 3.1. Para Yatırma İsteği (Deposit Request)
Kullanıcılarınızın sisteme para yatırma talebi oluşturması için kullanılır. Bu istek sonrası işlem **Bekliyor** statüsüne geçer. Operatör onayladığında Callback gönderilir.

*   **URL:** `/api/public/deposit-request/`
*   **Method:** `POST`
*   **Body Parameters (JSON):**

| Parametre | Tip | Zorunlu | Açıklama |
| :--- | :--- | :--- | :--- |
| `amount` | Decimal/String | **Evet** | Yatırılacak tutar (Örn: `"1500.00"`). |
| `full_name` | String | **Evet** | Gönderici Ad Soyad. |
| `user_id` | String | **Evet** | Sizin sisteminizdeki Kullanıcı ID (Unique ID). |
| `callback_url`| URL | Hayır | İşlem sonucunun bildirileceği Webhook URL'i. |

*   **Örnek JSON Request:**
```json
{
  "amount": "1500.00",
  "full_name": "Ahmet Yılmaz",
  "user_id": "USER_ID_12345",
  "callback_url": "https://sizin-siteniz.com/api/callback"
}
```

*   **Başarılı Yanıt (HTTP 200/201):**
```json
{
    "status": "success",
    "transaction_id": 105,
    "message": "Deposit request received."
}
```

### 3.2. Para Çekme İsteği (Withdraw Request)
Kullanıcının bakiyesini IBAN'a çekmesi için kullanılır.

*   **URL:** `/api/public/withdraw-request/`
*   **Method:** `POST`
*   **Body Parameters (JSON):**

| Parametre | Tip | Zorunlu | Açıklama |
| :--- | :--- | :--- | :--- |
| `amount` | Decimal/String | **Evet** | Çekilecek tutar. |
| `customer_iban`| String | **Evet** | TR ile başlayan IBAN (Boşluksuz). |
| `customer_name`| String | **Evet** | Alıcı Ad Soyad. |
| `external_id` | String | **Evet** | Sizin sisteminizdeki benzersiz İşlem ID'si. |
| `callback_url` | URL | Hayır | İşlem sonucunun bildirileceği Webhook URL'i. |

*   **Örnek JSON Request:**
```json
{
  "amount": "5000.00",
  "customer_iban": "TR120006200000012345678901",
  "customer_name": "Mehmet Demir",
  "external_id": "TXN_998877",
  "callback_url": "https://sizin-siteniz.com/api/callback"
}
```

---

## 4. Callback / Webhook Yapısı
Bir işlemin durumu (Onay/Ret) değiştiğinde, isteği gönderirken belirttiğiniz `callback_url` adresine sistemimiz tarafından **POST** isteği gönderilir.

*   **Method:** `POST`
*   **Content-Type:** `application/json`

**Payload (JSON):**
```json
{
  "transaction_id": 105,        // NexKasa Sistem ID'si
  "status": "APPROVED",         // Durum: APPROVED veya REJECTED
  "external_id": "USER_ID_12345", // Sizin gönderdiğiniz ID (user_id veya external_id)
  "amount": "1500.00",
  "type": "DEPOSIT"             // DEPOSIT veya WITHDRAW
}
```

### Status Değerleri:
*   `APPROVED`: İşlem onaylandı, bakiye güncellendi/para gönderildi.
*   `REJECTED`: İşlem iptal edildi veya reddedildi.
*   `WAITING_ASSIGNMENT`: (Sadece Withdraw) İşlem havuzda bekliyor (Opsiyonel bildirim).

### Önemli Notlar:
1.  **Response:** Callback isteğini aldığınızda sunucunuz `200 OK` HTTP kodu dönmelidir. Aksi takdirde (örn: 500 hatası) sistem isteği tekrar göndermeyi deneyebilir (Retry mekanizması varsa).
2.  **Güvenlik:** Callback isteğinin NexKasa sunucusundan geldiğini doğrulamak için IP kontrolü yapabilir veya URL'nize gizli bir token (query param) ekleyebilirsiniz (Örn: `?token=SECRET`).

---

## 5. Hata Kodları (HTTP Status)
*   `200 OK`: İşlem Başarılı.
*   `400 Bad Request`: Eksik veya hatalı parametre.
*   `403 Forbidden`: Geçersiz API Key veya IP kısıtlaması.
*   `409 Conflict`: Mükerrer işlem (Aynı ID ile bekleyen işlem varsa).
*   `500 Internal Server Error`: Sunucu hatası.
