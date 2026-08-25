import AVFoundation
import CoreAudio
import CoreGraphics
import Foundation

private enum AudioTapError: Error {
    case capturePermission
    case tapCreate(OSStatus)
    case aggregateCreate(OSStatus)
    case ioStart(OSStatus)
    case unsupportedAudioFormat
}

@available(macOS 14.2, *)
private final class SystemTap {
    private let queue = DispatchQueue(label: "AudioTap.io")
    private var tapID = AudioObjectID(kAudioObjectUnknown)
    private var aggregateID = AudioObjectID(kAudioObjectUnknown)
    private var ioProcID: AudioDeviceIOProcID?
    private var asbd = AudioStreamBasicDescription()

    func start() throws {
        guard CGPreflightScreenCaptureAccess() || CGRequestScreenCaptureAccess() else {
            throw AudioTapError.capturePermission
        }

        let uuid = UUID()
        let description = CATapDescription(stereoGlobalTapButExcludeProcesses: [])
        description.uuid = uuid
        description.isPrivate = true
        description.muteBehavior = .unmuted

        var tap = AudioObjectID(kAudioObjectUnknown)
        let tapStatus = AudioHardwareCreateProcessTap(description, &tap)
        guard tapStatus == noErr, tap != kAudioObjectUnknown else {
            throw AudioTapError.tapCreate(tapStatus)
        }
        tapID = tap

        var formatSize = UInt32(MemoryLayout<AudioStreamBasicDescription>.size)
        var formatAddress = AudioObjectPropertyAddress(
            mSelector: kAudioTapPropertyFormat,
            mScope: kAudioObjectPropertyScopeGlobal,
            mElement: kAudioObjectPropertyElementMain
        )
        let formatStatus = AudioObjectGetPropertyData(
            tapID,
            &formatAddress,
            0,
            nil,
            &formatSize,
            &asbd
        )
        guard formatStatus == noErr else {
            throw AudioTapError.tapCreate(formatStatus)
        }

        let aggregateDescription: [String: Any] = [
            kAudioAggregateDeviceNameKey: "QuestRock System Audio Tap",
            kAudioAggregateDeviceUIDKey: UUID().uuidString,
            kAudioAggregateDeviceIsPrivateKey: true,
            kAudioAggregateDeviceTapAutoStartKey: true,
            kAudioAggregateDeviceTapListKey: [
                [
                    kAudioSubTapUIDKey: uuid.uuidString,
                    kAudioSubTapDriftCompensationKey: true,
                ],
            ],
        ]
        var aggregate = AudioObjectID(kAudioObjectUnknown)
        let aggregateStatus = AudioHardwareCreateAggregateDevice(
            aggregateDescription as CFDictionary,
            &aggregate
        )
        guard aggregateStatus == noErr, aggregate != kAudioObjectUnknown else {
            throw AudioTapError.aggregateCreate(aggregateStatus)
        }
        aggregateID = aggregate

        let sampleRate = Int(asbd.mSampleRate.rounded())
        FileHandle.standardOutput.write(
            Data("{\"sample_rate\":\(sampleRate),\"channels\":2,\"format\":\"s16le\"}\n".utf8)
        )

        var ioProc: AudioDeviceIOProcID?
        let ioStatus = AudioDeviceCreateIOProcIDWithBlock(&ioProc, aggregateID, queue) {
            [self] _, inputData, _, _, _ in
            self.writePCM(from: inputData)
        }
        guard ioStatus == noErr, let ioProc else {
            throw AudioTapError.ioStart(ioStatus)
        }
        ioProcID = ioProc

        let startStatus = AudioDeviceStart(aggregateID, ioProc)
        guard startStatus == noErr else {
            throw AudioTapError.ioStart(startStatus)
        }
    }

    private func writePCM(from inputData: UnsafePointer<AudioBufferList>) {
        let buffers = UnsafeMutableAudioBufferListPointer(UnsafeMutablePointer(mutating: inputData))
        let channels = max(1, Int(asbd.mChannelsPerFrame))
        let bytesPerSample = max(1, Int(asbd.mBitsPerChannel / 8))
        let isFloat = (asbd.mFormatFlags & kAudioFormatFlagIsFloat) != 0
        let frameCount: Int
        if buffers.count > 0 {
            frameCount = Int(buffers[0].mDataByteSize) / max(1, bytesPerSample * (buffers.count == 1 ? channels : 1))
        } else {
            return
        }
        guard frameCount > 0 else {
            return
        }

        var output = Data(count: frameCount * 4)
        output.withUnsafeMutableBytes { destination in
            let samples = destination.bindMemory(to: Int16.self)
            for frame in 0..<frameCount {
                let left = sample(buffers: buffers, frame: frame, channel: 0, channels: channels, bytesPerSample: bytesPerSample, isFloat: isFloat)
                let right = channels > 1
                    ? sample(buffers: buffers, frame: frame, channel: 1, channels: channels, bytesPerSample: bytesPerSample, isFloat: isFloat)
                    : left
                samples[frame * 2] = left
                samples[frame * 2 + 1] = right
            }
        }
        FileHandle.standardOutput.write(output)
    }

    private func sample(
        buffers: UnsafeMutableAudioBufferListPointer,
        frame: Int,
        channel: Int,
        channels: Int,
        bytesPerSample: Int,
        isFloat: Bool
    ) -> Int16 {
        let nonInterleaved = buffers.count > 1
        let bufferIndex = nonInterleaved ? channel : 0
        guard bufferIndex < buffers.count, let data = buffers[bufferIndex].mData else {
            return 0
        }
        let index = nonInterleaved ? frame : frame * channels + channel
        let pointer = data.advanced(by: index * bytesPerSample)
        if isFloat, bytesPerSample == 4 {
            let bits = pointer.loadUnaligned(as: UInt32.self)
            return floatToS16(Float(bitPattern: bits))
        }
        if !isFloat, bytesPerSample == 2 {
            return Int16(bitPattern: pointer.loadUnaligned(as: UInt16.self))
        }
        return 0
    }

    private func floatToS16(_ value: Float) -> Int16 {
        Int16((max(-1, min(1, value)) * 32_767).rounded())
    }
}

private func writeError(_ message: String) {
    FileHandle.standardError.write(Data("\(message)\n".utf8))
}

private var retainedTap: SystemTap?

@main
private struct Main {
    static func main() {
        guard #available(macOS 14.2, *) else {
            writeError("capture_error: macOS 14.2 or later is required")
            Darwin.exit(1)
        }
        do {
            let tap = SystemTap()
            retainedTap = tap
            try tap.start()
            dispatchMain()
        } catch AudioTapError.capturePermission {
            writeError("capture_permission")
            Darwin.exit(1)
        } catch AudioTapError.tapCreate {
            writeError("capture_permission")
            Darwin.exit(1)
        } catch {
            writeError("capture_error: \(error)")
            Darwin.exit(1)
        }
    }
}
