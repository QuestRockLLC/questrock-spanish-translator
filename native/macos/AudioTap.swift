import AudioToolbox
import CoreGraphics
import CoreMedia
import Foundation
import ScreenCaptureKit

private enum AudioTapError: Error {
    case capturePermission
    case noDisplay
    case unsupportedAudioFormat
}

private final class AudioTap: NSObject, SCStreamDelegate, SCStreamOutput {
    private let audioQueue = DispatchQueue(label: "AudioTap.audio")
    private let screenQueue = DispatchQueue(label: "AudioTap.screen")
    private var stream: SCStream?

    func start() async throws {
        guard CGPreflightScreenCaptureAccess() || CGRequestScreenCaptureAccess() else {
            throw AudioTapError.capturePermission
        }

        let content: SCShareableContent
        do {
            content = try await SCShareableContent.excludingDesktopWindows(
                false,
                onScreenWindowsOnly: false
            )
        } catch {
            if !CGPreflightScreenCaptureAccess() {
                throw AudioTapError.capturePermission
            }
            throw error
        }

        guard let display = content.displays.first else {
            throw AudioTapError.noDisplay
        }

        let configuration = SCStreamConfiguration()
        configuration.capturesAudio = true
        configuration.excludesCurrentProcessAudio = true
        configuration.sampleRate = 48_000
        configuration.channelCount = 2
        configuration.width = 2
        configuration.height = 2
        configuration.minimumFrameInterval = CMTime(value: 1, timescale: 1)
        configuration.showsCursor = false

        let stream = SCStream(
            filter: SCContentFilter(display: display, excludingWindows: []),
            configuration: configuration,
            delegate: self
        )
        try stream.addStreamOutput(self, type: .audio, sampleHandlerQueue: audioQueue)
        try stream.addStreamOutput(self, type: .screen, sampleHandlerQueue: screenQueue)
        self.stream = stream

        FileHandle.standardOutput.write(
            Data("{\"sample_rate\":48000,\"channels\":2,\"format\":\"s16le\"}\n".utf8)
        )
        try await stream.startCapture()
    }

    func stream(
        _ stream: SCStream,
        didOutputSampleBuffer sampleBuffer: CMSampleBuffer,
        of outputType: SCStreamOutputType
    ) {
        guard outputType == .audio, sampleBuffer.isValid else {
            return
        }

        do {
            if let pcm = try convertToS16LE(sampleBuffer), !pcm.isEmpty {
                FileHandle.standardOutput.write(pcm)
            }
        } catch {
            writeError("audio_conversion: \(error)")
            Darwin.exit(1)
        }
    }

    func stream(_ stream: SCStream, didStopWithError error: Error) {
        if !CGPreflightScreenCaptureAccess() {
            writeError("capture_permission")
        } else {
            writeError("capture_stopped: \(error)")
        }
        Darwin.exit(1)
    }

    private func convertToS16LE(_ sampleBuffer: CMSampleBuffer) throws -> Data? {
        guard
            let formatDescription = sampleBuffer.formatDescription,
            let description = CMAudioFormatDescriptionGetStreamBasicDescription(formatDescription)
        else {
            return nil
        }

        let format = description.pointee
        guard format.mFormatID == kAudioFormatLinearPCM else {
            throw AudioTapError.unsupportedAudioFormat
        }

        let channels = Int(format.mChannelsPerFrame)
        let frameCount = sampleBuffer.numSamples
        guard channels > 0, frameCount > 0 else {
            return nil
        }

        let bufferListSize = MemoryLayout<AudioBufferList>.size
            + (channels - 1) * MemoryLayout<AudioBuffer>.size
        let storage = UnsafeMutableRawPointer.allocate(
            byteCount: bufferListSize,
            alignment: MemoryLayout<AudioBufferList>.alignment
        )
        defer { storage.deallocate() }

        let bufferList = storage.bindMemory(to: AudioBufferList.self, capacity: 1)
        bufferList.initialize(
            to: AudioBufferList(
                mNumberBuffers: 0,
                mBuffers: AudioBuffer(mNumberChannels: 0, mDataByteSize: 0, mData: nil)
            )
        )
        var retainedBlockBuffer: CMBlockBuffer?
        let status = CMSampleBufferGetAudioBufferListWithRetainedBlockBuffer(
            sampleBuffer,
            bufferListSizeNeededOut: nil,
            bufferListOut: bufferList,
            bufferListSize: bufferListSize,
            blockBufferAllocator: kCFAllocatorDefault,
            blockBufferMemoryAllocator: kCFAllocatorDefault,
            flags: 0,
            blockBufferOut: &retainedBlockBuffer
        )
        guard status == noErr else {
            throw NSError(domain: NSOSStatusErrorDomain, code: Int(status))
        }

        let buffers = UnsafeMutableAudioBufferListPointer(bufferList)
        let flags = format.mFormatFlags
        let nonInterleaved = flags & kAudioFormatFlagIsNonInterleaved != 0
        let isFloat = flags & kAudioFormatFlagIsFloat != 0
        let isSignedInteger = flags & kAudioFormatFlagIsSignedInteger != 0
        let isBigEndian = flags & kAudioFormatFlagIsBigEndian != 0
        let bytesPerSample = Int(format.mBitsPerChannel / 8)

        guard
            channels == 2,
            bytesPerSample > 0,
            (isFloat || isSignedInteger),
            buffers.count >= (nonInterleaved ? channels : 1)
        else {
            throw AudioTapError.unsupportedAudioFormat
        }

        var output = Data(count: frameCount * channels * MemoryLayout<Int16>.size)
        try output.withUnsafeMutableBytes { destination in
            let samples = destination.bindMemory(to: Int16.self)
            for frame in 0..<frameCount {
                for channel in 0..<channels {
                    let bufferIndex = nonInterleaved ? channel : 0
                    let sampleIndex = nonInterleaved ? frame : frame * channels + channel
                    guard let source = buffers[bufferIndex].mData else {
                        throw AudioTapError.unsupportedAudioFormat
                    }
                    let pointer = source.advanced(by: sampleIndex * bytesPerSample)
                    let value = try normalizedSample(
                        at: pointer,
                        bytesPerSample: bytesPerSample,
                        isFloat: isFloat,
                        isBigEndian: isBigEndian
                    )
                    let scaled = Int16((max(-1, min(1, value)) * 32_767).rounded())
                    samples[frame * channels + channel] = scaled.littleEndian
                }
            }
        }
        return output
    }

    private func normalizedSample(
        at pointer: UnsafeMutableRawPointer,
        bytesPerSample: Int,
        isFloat: Bool,
        isBigEndian: Bool
    ) throws -> Double {
        if isFloat, bytesPerSample == 4 {
            let bits = pointer.loadUnaligned(as: UInt32.self)
            return Double(Float(bitPattern: isBigEndian ? bits.byteSwapped : bits))
        }
        if isFloat, bytesPerSample == 8 {
            let bits = pointer.loadUnaligned(as: UInt64.self)
            return Double(bitPattern: isBigEndian ? bits.byteSwapped : bits)
        }
        if !isFloat, bytesPerSample == 2 {
            let bits = pointer.loadUnaligned(as: UInt16.self)
            let value = Int16(bitPattern: isBigEndian ? bits.byteSwapped : bits)
            return Double(value) / 32_768
        }
        if !isFloat, bytesPerSample == 4 {
            let bits = pointer.loadUnaligned(as: UInt32.self)
            let value = Int32(bitPattern: isBigEndian ? bits.byteSwapped : bits)
            return Double(value) / 2_147_483_648
        }
        throw AudioTapError.unsupportedAudioFormat
    }
}

private func writeError(_ message: String) {
    FileHandle.standardError.write(Data("\(message)\n".utf8))
}

@main
private struct Main {
    static func main() async {
        let tap = AudioTap()
        do {
            try await tap.start()
            dispatchMain()
        } catch AudioTapError.capturePermission {
            writeError("capture_permission")
            Darwin.exit(1)
        } catch {
            writeError("capture_error: \(error)")
            Darwin.exit(1)
        }
    }
}
