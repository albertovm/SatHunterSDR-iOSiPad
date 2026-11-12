import AVFoundation
import SatHunterCore

final class AudioOutput {
    private final class VolumeBox { var value: Float = 1 }
    private let engine = AVAudioEngine()
    private let volumeBox = VolumeBox()
    private var source: AVAudioSourceNode?
    var isRunning: Bool { engine.isRunning }

    func start() {
        if source != nil {
            if !engine.isRunning {
                try? AVAudioSession.sharedInstance().setActive(true)
                try? engine.start()
            }
            return
        }
        let format = AVAudioFormat(standardFormatWithSampleRate: 48_000, channels: 1)!
        let volumeBox = self.volumeBox
        let node = AVAudioSourceNode(format: format) { _, _, frameCount, audioBufferList in
            let buffers = UnsafeMutableAudioBufferListPointer(audioBufferList)
            for buffer in buffers {
                guard let data = buffer.mData else { continue }
                let destination = data.assumingMemoryBound(to: Float.self)
                let capacity = Int(buffer.mDataByteSize) / MemoryLayout<Float>.stride
                let requested = min(capacity, Int(frameCount))
                let count = sh_apple_audio(destination, requested)
                for index in 0..<count { destination[index] *= volumeBox.value }
                if count < capacity { for index in count..<capacity { destination[index] = 0 } }
            }
            return noErr
        }
        engine.attach(node); engine.connect(node, to: engine.mainMixerNode, format: format)
        source = node
        try? AVAudioSession.sharedInstance().setCategory(.playback, mode: .default, options: [.allowBluetoothA2DP])
        try? AVAudioSession.sharedInstance().setActive(true)
        try? engine.start()
    }

    func setVolume(_ value: Float) { volumeBox.value = max(0, min(1, value)) }

    func stop() { engine.stop(); if let node = source { engine.detach(node) }; source = nil }
}
