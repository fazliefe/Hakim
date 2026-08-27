import Link from "next/link";

export function KvkkScreen() {
  return (
    <main className="kvkk-screen">
      <div className="kvkk-card">
        <Link href="/giris" className="kvkk-back">
          ← Girişe dön
        </Link>
        <h1>KVKK Aydınlatma Metni</h1>
        <p className="kvkk-updated">Son güncelleme: [tarih girilecek]</p>

        <p className="kvkk-todo">
          <strong>Not:</strong> Bu metin, geliştirici tarafından hazırlanan bir taslaktır; yayına
          alınmadan önce veri sorumlusunun kimliği, iletişim bilgileri ve saklama süreleri
          doldurulmalı, içerik bir hukuk danışmanınca gözden geçirilmelidir.
        </p>

        <section>
          <h2>1. Veri Sorumlusu</h2>
          <p>
            6698 sayılı Kişisel Verilerin Korunması Kanunu ("KVKK") uyarınca, HÂKİM uygulaması
            kapsamında işlenen kişisel verileriniz bakımından veri sorumlusu{" "}
            <strong>[proje/kurum adı girilecek]</strong>'dir. İletişim: <strong>[e-posta/adres girilecek]</strong>.
          </p>
        </section>

        <section>
          <h2>2. İşlenen Kişisel Veriler</h2>
          <ul>
            <li>Hesap bilgileri: kullanıcı adı, e-posta adresi, şifrelenmiş parola.</li>
            <li>
              Yüklediğiniz evrak/dilekçe metinleri ve bu metinlerden çıkarılan bilgiler (ad-soyad,
              T.C. kimlik no, adres, dava/mahkeme bilgileri gibi belgede yer alan veriler).
            </li>
            <li>Oturum ve işlem kayıtları (giriş zamanı, üretilen belge türü gibi kullanım logları).</li>
          </ul>
        </section>

        <section>
          <h2>3. İşlenme Amacı</h2>
          <p>
            Kişisel verileriniz; hesabınızın oluşturulması ve yönetilmesi, yüklediğiniz evrakın
            analiz edilerek dilekçe/resmi yazı taslağı üretilmesi, ilgili mevzuat ve süre
            hesaplarının çıkarılması ve hizmetin güvenliğinin sağlanması amaçlarıyla işlenir.
          </p>
        </section>

        <section>
          <h2>4. Yapay Zekâ Servislerine Aktarım</h2>
          <p>
            Taslak üretimi için yüklediğiniz metin, büyük dil modeli (LLM) sağlayan üçüncü taraf
            servislere iletilir. Bilinen kimlik numarası, IBAN, e-posta ve telefon gibi bazı
            doğrudan tanımlayıcılar bu gönderim öncesinde otomatik olarak maskelenir; ancak
            dilekçenin hukuken geçerli olabilmesi için ad-soyad, T.C. kimlik no gibi bazı alanlar
            (belgeden çıkarılan yapılandırılmış alanlar) maskelenmeden gönderilir. Kullanılan
            sağlayıcı(lar) ve veri saklama politikaları: <strong>[doldurulacak]</strong>.
          </p>
          <p>
            Ayrıca, sistemin doğru çalışıp çalışmadığını izlemek (gözlemlenebilirlik) amacıyla bu
            istekler <strong>Langfuse</strong> (ABD merkezli bulut servisi) üzerinden kaydedilebilir;
            bu kayıtlar da yukarıdaki maskeleme kuralına tabidir ve yalnızca teknik ekip erişimine
            açıktır.
          </p>
        </section>

        <section>
          <h2>5. Saklama Süresi</h2>
          <p>
            Kişisel verileriniz, hesabınız aktif olduğu sürece ve ilgili mevzuattan doğan
            yükümlülükler saklı kalmak kaydıyla <strong>[saklama süresi girilecek]</strong> boyunca
            saklanır; hesabınızı sildiğinizde ilişkili veriler silinir/anonimleştirilir.
          </p>
        </section>

        <section>
          <h2>6. Haklarınız (KVKK m.11)</h2>
          <p>
            KVKK'nın 11. maddesi uyarınca; kişisel verilerinizin işlenip işlenmediğini öğrenme,
            işlenmişse buna ilişkin bilgi talep etme, işlenme amacını ve amacına uygun kullanılıp
            kullanılmadığını öğrenme, yurt içinde/yurt dışında aktarıldığı üçüncü kişileri bilme,
            eksik/yanlış işlenmişse düzeltilmesini isteme, silinmesini/yok edilmesini isteme ve
            kanuna aykırı işleme sebebiyle zarara uğramanız hâlinde zararın giderilmesini talep
            etme haklarına sahipsiniz. Taleplerinizi <strong>[iletişim kanalı girilecek]</strong>{" "}
            üzerinden iletebilirsiniz.
          </p>
        </section>

        <section>
          <h2>7. Önemli Uyarı</h2>
          <p>
            HÂKİM tarafından üretilen taslak metinler yapay zekâ tarafından oluşturulur ve hukuki
            tavsiye niteliği taşımaz. Üretilen içerik resmi bir kuruma sunulmadan önce mutlaka
            kendiniz veya bir avukat tarafından doğrulanmalıdır.
          </p>
        </section>
      </div>
    </main>
  );
}
