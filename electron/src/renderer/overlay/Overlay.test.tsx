import { render, screen } from '@testing-library/react'
import { Overlay } from './Overlay'

it('shows English primary and Spanish verifier', () => {
  render(
    <Overlay
      status="Listening"
      originalText="Estoy buscando refinanciar mi casa porque mi pago mensual es muy alto."
      translatedText="I am looking to refinance my home because my monthly payment is very high."
    />,
  )
  expect(screen.getByText('QuestRock')).toBeTruthy()
  expect(screen.getByText('Listening')).toBeTruthy()
  expect(document.querySelector('.english')?.textContent).toMatch(/I am looking to refinance/)
  expect(document.querySelector('.spanish')?.textContent).toMatch(/Estoy buscando refinanciar/)
})

it('shows Translation unavailable when translatedText is null', () => {
  render(<Overlay status="Listening" originalText="Hola" translatedText={null} />)
  expect(screen.getByText('Translation unavailable')).toBeTruthy()
})
