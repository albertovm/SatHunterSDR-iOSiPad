import AVFoundation
import SatHunterCore

final class AudioOutput {
    private final class VolumeBox { var value: Float = 1 }
    private let engine = AVAudioEngine()
    private let volumeBox = VolumeBox()
    private var source: AVAudioSourceNode?

    func start() {
        guard source == nil else { return }
        let format = AVAudioFormat(standardFormatWithSampleRate: 48_000, channels: 1)!
        let volumeBox = self.volumeBox
        let node = AVAudioSourceNode(format: format) { _, _, frameCount, audioBufferList in
            let buffers = UnsafeMutableAudioBufferListPointer(audioBufferList)
            var samples = [Float](repeating: 0, count: Int(frameCount))
            let count = sh_apple_audio(&samples, samples.count)
            for buffer in buffers {
                guard let data = buffer.mData else { continue }
                samples.withUnsafeBufferPointer { source in
                    let destination = data.assumingMemoryBound(to: Float.self)
                    let limit = min(Int(buffer.mDataByteSize) / MemoryLayout<Float>.stride, count)
                    for index in 0..<limit { destination[index] = source[index] * volumeBox.value }
                }
            }
            return noErr
        }
        engine.attach(node); engine.connect(node, to: engine.mainMixerNode, format: format)
        source = node
        try? AVAudioSession.sharedInstance().setCategory(.playAndRecord, options: [.defaultToSpeaker, .allowBluetoothHFP])
        try? AVAudioSession.sharedInstance().setActive(true)
        try? engine.start()
    }

    func setVolume(_ value: Float) { volumeBox.value = max(0, min(1, value)) }

    func stop() { engine.stop(); if let node = source { engine.detach(node) }; source = nil }
}
