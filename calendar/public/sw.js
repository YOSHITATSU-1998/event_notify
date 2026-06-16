3// 最小限のサービスワーカー (PWA認識用ダミー)
// 開発中の強力なキャッシュによるデータ更新遅延を防ぐため、通信をキャッシュせずそのままスルーします。

const CACHE_NAME = 'fukuoka-events-v1';

self.addEventListener('install', (event) => {
  // インストール時に即座にアクティブにする
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  // 古いキャッシュのクリーンアップなど（現時点では空）
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  // PWAの条件を満たすためのフェッチハンドラー（何もしないで素通しする）
  // これにより、サイト上の最新イベントやバナーデータが常にネットワークから直接ロードされます。
  return;
});
