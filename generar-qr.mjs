// Genera los códigos QR del menú: uno general y uno por mesa (?mesa=N).
// Uso: npm run qr -- https://menu.tudominio.com 12
import { mkdirSync } from 'node:fs'
import QRCode from 'qrcode'

const [, , urlBase, totalMesas = '10'] = process.argv

if (!urlBase || !urlBase.startsWith('https://')) {
  console.error('Uso: npm run qr -- https://menu.tudominio.com 12')
  console.error('La URL debe ser pública y empezar con https:// (nunca localhost ni una IP local).')
  process.exit(1)
}

const base = urlBase.replace(/\/$/, '')
const opciones = {
  width: 1024,
  margin: 2,
  errorCorrectionLevel: 'H', // tolera rayones y desgaste
  color: { dark: '#000000', light: '#FFFFFF' }, // negro sobre blanco: lo leen todos los celulares
}

mkdirSync('qr', { recursive: true })
await QRCode.toFile('qr/menu-general.png', `${base}/`, opciones)

for (let mesa = 1; mesa <= Number(totalMesas); mesa++) {
  const archivo = `qr/mesa-${String(mesa).padStart(2, '0')}.png`
  await QRCode.toFile(archivo, `${base}/?mesa=${mesa}`, opciones)
}
console.log(`Listo: qr/menu-general.png y ${totalMesas} QR de mesa en la carpeta qr/`)
