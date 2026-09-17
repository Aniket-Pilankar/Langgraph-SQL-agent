import { useRef, useState } from 'react'

export function useVoice() {
  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const recognitionRef = useRef<SpeechRecognitionInstance | null>(null)

  const SpeechRecognition =
    typeof window !== 'undefined' ? window.SpeechRecognition || window.webkitSpeechRecognition : undefined
  const isSupported = Boolean(SpeechRecognition)

  function start() {
    if (!SpeechRecognition || isListening) return

    const recognition = new SpeechRecognition()
    recognition.lang = 'en-US'
    recognition.continuous = true
    recognition.interimResults = true

    recognition.onresult = event => {
      let text = ''
      for (let i = 0; i < event.results.length; i++) {
        text += event.results[i][0].transcript
      }
      setTranscript(text)
    }
    recognition.onend = () => setIsListening(false)
    recognition.onerror = () => setIsListening(false)

    recognitionRef.current = recognition
    setTranscript('')
    recognition.start()
    setIsListening(true)
  }

  function stop() {
    recognitionRef.current?.stop()
    setIsListening(false)
  }

  return { isSupported, isListening, transcript, start, stop }
}
