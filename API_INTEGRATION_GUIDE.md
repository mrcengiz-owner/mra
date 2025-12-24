# PayGate Entegrasyon Dökümantasyonu (v1.0)

Bu döküman, PayGate sistemine dışarıdan yatırım (Deposit) talebi göndermek ve bu talepleri onaylamak için gereken API uç noktalarını açıklar.

## 1. Giriş ve Güvenlik

PayGate API, güvenliği en üst düzeyde tutmak için **API Key** ve **IP Whitelisting** yöntemlerini kullanır.

*   **Base URL:** `https://api.yourdomain.com/web/api/public/`
*   **Güvenlik Protokolü:** Tüm istekler HTTPS üzerinden yapılmalıdır.
*   **Yetkilendirme:** Tüm isteklerin Header kısmında size özel tanımlanan API Key gönderilmelidir.

### Header Parametreleri
| Key | Değer | Açıklama |
| :--- | :--- | :--- |
| `X-API-KEY` | `Sizin_API_Keyiniz` | Admin tarafından size iletilen 64 karakterlik anahtar. |
| `Content-Type` | `application/json` | Veri formatı her zaman JSON olmalıdır. |

> **Önemli Not:** API erişimi için sunucu IP adreslerinizin sistemimize tanımlanmış olması gerekmektedir. Tanımlı olmayan IP'lerden gelen istekler `403 Forbidden` hatası ile reddedilecektir.

---

## 2. API Uç Noktaları

### 2.1 Yatırım İsteği (Deposit Request)
Kullanıcının yatırım yapmak istediği miktarı ileterek uygun bir banka hesabı ve işlem tokenı almak için kullanılır.

*   **URL:** `/deposit-request/`
*   **Method:** `POST`

#### İstek Parametreleri (JSON)
| Parametre | Tip | Açıklama |
| :--- | :--- | :--- |
| `full_name` | String | Yatırım yapacak kullanıcının Adı Soyadı. |
| `amount` | Decimal | Yatırım miktarı (Örn: 1500.00). |
| `user_id` | String | Sizin sisteminizdeki benzersiz kullanıcı ID'si. |

#### Örnek İstek (Curl)
```bash
curl -X POST https://api.yourdomain.com/web/api/public/deposit-request/ \
     -H "X-API-KEY: 64_karakterlik_api_keyiniz" \
     -H "Content-Type: application/json" \
     -d '{
       "full_name": "Ahmet Yılmaz",
       "amount": 2500.00,
       "user_id": "USER_12345"
     }'
```

#### Başarılı Yanıt (201 Created)
```json
{
    "status": "success",
    "transaction_token": "a1b2c3d4-e5f6...",
    "banka_bilgileri": {
        "banka_adi": "Ziraat Bankası",
        "alici_adi": "PayGate Finans LTD",
        "iban": "TR00 0000 0000 0000 0000 00"
    }
}
```

#### Hata Yanıtı (404 Not Found - Limit Sorunu)
```json
{
    "error": "Uygun hesap bulunamadı (Limitler dolu veya limit dışı miktar)."
}
```

---

### 2.2 Yatırım Onayı (Deposit Confirm)
Kullanıcı transferi gerçekleştirdikten sonra, işlemin onay kuyruğuna alınması için bu endpoint çağrılmalıdır.

*   **URL:** `/deposit-confirm/`
*   **Method:** `POST`

#### İstek Parametreleri (JSON)
| Parametre | Tip | Açıklama |
| :--- | :--- | :--- |
| `transaction_token` | UUID | İlk istekten dönen benzersiz işlem anahtarı. |

#### Örnek İstek
```json
{
    "transaction_token": "a1b2c3d4-e5f6..."
}
```

#### Başarılı Yanıt (200 OK)
```json
{
    "status": "confirmed",
    "message": "İşlem onaya gönderildi."
}
```

#### Hata Yanıtı (400 Bad Request)
```json
{
    "error": "İşlem iptal edilmiş veya geçersiz."
}
```

---

## 3. Durum Kodları

| Kod | Açıklama |
| :--- | :--- |
| `200/201` | İşlem başarılı. |
| `400` | Geçersiz parametre veya mantıksal hata. |
| `401` | Eksik veya hatalı API Key. |
| `403` | IP adresi yetkilendirilmemiş. |
| `404` | Kaynak veya uygun hesap bulunamadı. |
| `500` | Sunucu taraflı sistemsel hata. |
