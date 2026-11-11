import AVFoundation
import SatHunterCore

final class AudioOutput {
    private let engine = AVAudioEngine()
    private var source: AVAudioSourceNode?

    func start() {
        guard source == nil else { return }
        let format = AVAudioFormat(standardFormatWithSampleRate: 48_000, channels: 1)!
        let node = AVAudioSourceNode(format: format) { _, _, frameCount, audioBufferList in
            let buffers = UnsafeMutableAudioBufferListPointer(audioBufferList)
            var samples = [Float](repeating: 0, count: Int(frameCount))
            let count = sh_apple_audio(&samples, samples.count)
            for buffer in buffers {
                guard let data = buffer.mData else { continue }
                samples.withUnsafeBufferPointer { source in
                    data.assumingMemoryBound(to: Float.self).assign(from: source.baseAddress!, count: min(Int(buffer.mDataByteSize) / MemoryLayout<Float>.stride, count))
                }
            }
            return noErr
        }
        engine.attach(node); engine.connect(node, to: engine.mainMixerNode, format: format)
        source = node
        try? AVAudioSession.sharedInstance().setCategory(.playAndRecord, options: [.defaultToSpeaker, .allowBluetooth])
        try? AVAudioSession.sharedInstance().setActive(true)
        try? engine.start()
    }

    func stop() { engine.stop(); if let node = source { engine.detach(node) }; source = nil }
}
