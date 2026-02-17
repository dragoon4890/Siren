# audio_processor.py - Batch Audio Processing with Voice Conversion
import os
import base64
import json
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
import argparse
from typing import Optional, Tuple
import time

class AudioProcessor:
    def __init__(self, 
                 input_folder: str, 
                 output_folder: str,
                 server_url: str = "http://localhost:9090",
                 rvc_url: str = "http://127.0.0.1:5000",
                 target_lang: str = "ja"):
        """
        Initialize the audio processor
        
        Args:
            input_folder: Path to folder containing audio files to process
            output_folder: Path to folder where converted files will be saved
            server_url: URL of the translation server
            rvc_url: URL of the RVC/Seed-VC server
            target_lang: Target language code for translation
        """
        self.input_folder = Path(input_folder)
        self.output_folder = Path(output_folder)
        self.server_url = server_url
        self.rvc_url = rvc_url
        self.target_lang = target_lang
        
        # Create output folder if it doesn't exist
        self.output_folder.mkdir(parents=True, exist_ok=True)
        
        # Supported audio formats
        self.supported_formats = {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.aac'}
        
        # Session for HTTP requests - will be created per process
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Semaphore for RVC server (likely single-threaded)
        self.rvc_semaphore = asyncio.Semaphore(1)  # Limit RVC to 1 concurrent request
    
    async def __aenter__(self):
        """Async context manager entry"""
        # Create session with connection limits for better concurrency
        connector = aiohttp.TCPConnector(
            limit=100,  # Total connection pool size
            limit_per_host=20,  # Max connections per host
            ttl_dns_cache=300,  # DNS cache TTL
            use_dns_cache=True,
        )
        self.session = aiohttp.ClientSession(connector=connector)
        
        # Initialize RVC semaphore
        self.rvc_semaphore = asyncio.Semaphore(1)  # Only 1 concurrent RVC request
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
    
    async def blob_to_base64(self, file_path: Path) -> str:
        """Convert audio file to base64 string"""
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()
                return base64.b64encode(content).decode('utf-8')
        except Exception as e:
            print(f"Error reading file {file_path}: {e}")
            raise
    
    async def base64_to_blob(self, base64_data: str) -> bytes:
        """Convert base64 string to bytes"""
        try:
            return base64.b64decode(base64_data)
        except Exception as e:
            print(f"Error decoding base64 data: {e}")
            raise
    
    async def process_audio_translation(self, audio_file: Path) -> Tuple[str, bytes]:
        """
        Process audio through translation pipeline (same logic as JavaScript)
        
        Args:
            audio_file: Path to the audio file
            
        Returns:
            Tuple of (translated_text, translated_audio_blob)
        """
        print(f"  • Processing audio translation for {audio_file.name}...")
        
        try:
            # Convert audio to base64 (same as blobToBase64 in JS)
            audio_base64 = await self.blob_to_base64(audio_file)
            
            # Prepare request payload (same structure as JS fetch)
            payload = {
                'audio_blob': audio_base64,
                'source_lang': 'auto',  # auto-detect
                'target_lang': self.target_lang
            }
            
            # Send request to translation server (same as JS fetch call)
            async with self.session.post(
                f'{self.server_url}/process_audio',
                headers={'Content-Type': 'application/json'},
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                
                if not response.ok:
                    error_msg = f"Error processing audio: {response.status} {response.reason}"
                    print(f"    ❌ {error_msg}")
                    raise Exception(error_msg)
                
                result = await response.json()
                print(f"    ✅ Translation complete: \"{result.get('translated_text', 'N/A')}\"")
                
                # Extract results (same as JS result handling)
                translated_text = result.get('translated_text', '')
                translated_audio_base64 = result.get('translated_audio_blob', '')
                
                if not translated_audio_base64:
                    raise Exception("No translated audio received from server")
                
                # Convert base64 back to bytes (same as base64ToBlob in JS)
                translated_audio_blob = await self.base64_to_blob(translated_audio_base64)
                
                return translated_text, translated_audio_blob
                
        except Exception as e:
            print(f"    ❌ Translation error: {e}")
            raise
    
    async def apply_voice_conversion(self, 
                                   translated_audio: bytes, 
                                   reference_audio_file: Path) -> bytes:
        """
        Apply voice conversion using Seed-VC (same logic as JavaScript)
        
        Args:
            translated_audio: Translated audio bytes
            reference_audio_file: Original audio file for voice reference
            
        Returns:
            Voice-converted audio bytes
        """
        print(f"  • Applying voice conversion...")
        
        # Use semaphore to prevent concurrent RVC requests (critical fix!)
        async with self.rvc_semaphore:
            try:
                # Read reference audio (same as referenceBlob = audioBlob in JS)
                async with aiofiles.open(reference_audio_file, 'rb') as f:
                    reference_audio = await f.read()
                
                # Prepare FormData (same structure as JS FormData)
                data = aiohttp.FormData()
                data.add_field('input', 
                              translated_audio, 
                              filename='input.wav', 
                              content_type='audio/wav')
                data.add_field('reference', 
                              reference_audio, 
                              filename='reference.wav', 
                              content_type='audio/wav')
                
                # Send to Seed-VC server (same as JS fetch to Flask)
                async with self.session.post(
                    f'{self.rvc_url}/convert',
                    data=data,
                    timeout=aiohttp.ClientTimeout(total=120)  # RVC can take longer
                ) as response:
                    
                    if not response.ok:
                        error_msg = f"Error converting audio: {response.status} {response.reason}"
                        print(f"    ❌ {error_msg}")
                        raise Exception(error_msg)
                    
                    # Get converted audio (same as JS arrayBuffer handling)
                    converted_audio = await response.read()
                    print(f"    ✅ Voice conversion complete")
                    
                    return converted_audio
                    
            except Exception as e:
                print(f"    ❌ Voice conversion error: {e}")
                raise
    
    async def process_single_file(self, audio_file: Path) -> bool:
        """
        Process a single audio file through the complete pipeline
        
        Args:
            audio_file: Path to the audio file to process
            
        Returns:
            True if successful, False otherwise
        """
        start_time = time.time()
        print(f"\n🎵 Processing: {audio_file.name}")
        
        try:
            # Step 1: Translation (same as processAudio in JS)
            translated_text, translated_audio_blob = await self.process_audio_translation(audio_file)
            
            # Step 2: Voice Conversion - Use SAME audio file as reference (correct mapping)
            # This preserves the original speaker's voice in the translated audio
            final_audio = await self.apply_voice_conversion(translated_audio_blob, audio_file)
            
            # Step 3: Save converted audio (same naming as requested)
            output_filename = f"{audio_file.stem}_convert{audio_file.suffix}"
            output_path = self.output_folder / output_filename
            
            async with aiofiles.open(output_path, 'wb') as f:
                await f.write(final_audio)
            
            # Save metadata
            metadata = {
                'original_file': str(audio_file),
                'reference_voice_file': str(audio_file),  # Same file used as reference
                'translated_text': translated_text,
                'target_language': self.target_lang,
                'processing_time': time.time() - start_time
            }
            
            metadata_path = self.output_folder / f"{audio_file.stem}_convert_metadata.json"
            async with aiofiles.open(metadata_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(metadata, indent=2, ensure_ascii=False))
            
            processing_time = time.time() - start_time
            print(f"  ✅ Complete! Saved as: {output_filename} ({processing_time:.1f}s)")
            return True
            
        except Exception as e:
            processing_time = time.time() - start_time
            print(f"  ❌ Failed: {e} ({processing_time:.1f}s)")
            return False
    
    async def process_folder(self, max_concurrent: int = 3) -> dict:
        """
        Process all audio files in the input folder
        
        Args:
            max_concurrent: Maximum number of files to process concurrently
            
        Returns:
            Dictionary with processing statistics
        """
        # Find all audio files
        audio_files = []
        for ext in self.supported_formats:
            audio_files.extend(self.input_folder.glob(f"*{ext}"))
        
        if not audio_files:
            print(f"❌ No audio files found in {self.input_folder}")
            return {'total': 0, 'successful': 0, 'failed': 0}
        
        print(f"🚀 Found {len(audio_files)} audio files to process")
        print(f"📁 Input folder: {self.input_folder}")
        print(f"📁 Output folder: {self.output_folder}")
        print(f"🌍 Target language: {self.target_lang}")
        print(f"⚡ Max concurrent: {max_concurrent}")
        print(f"🎤 Each file will use its own voice as reference for conversion")
        print(f"🔒 RVC requests will be serialized to prevent server overload")
        
        # Process files with semaphore for concurrency control
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(file_path):
            async with semaphore:
                return await self.process_single_file(file_path)
        
        # Process all files
        start_time = time.time()
        results = await asyncio.gather(
            *[process_with_semaphore(file_path) for file_path in audio_files],
            return_exceptions=True
        )
        
        # Calculate statistics
        successful = sum(1 for result in results if result is True)
        failed = len(results) - successful
        total_time = time.time() - start_time
        
        print(f"\n📊 Processing Summary:")
        print(f"  Total files: {len(audio_files)}")
        print(f"  Successful: {successful}")
        print(f"  Failed: {failed}")
        print(f"  Total time: {total_time:.1f}s")
        print(f"  Average time per file: {total_time/len(audio_files):.1f}s")
        
        return {
            'total': len(audio_files),
            'successful': successful,
            'failed': failed,
            'total_time': total_time
        }

async def main():
    """Main function with CLI argument parsing"""
    parser = argparse.ArgumentParser(description='Batch Audio Translation and Voice Conversion')
    parser.add_argument('input_folder', help='Path to folder containing audio files')
    parser.add_argument('output_folder', help='Path to output folder for converted files')
    parser.add_argument('--target-lang', '-t', default='ja', 
                       help='Target language code (default: ja)')
    parser.add_argument('--server-url', '-s', default='http://localhost:9090',
                       help='Translation server URL (default: http://localhost:9090)')
    parser.add_argument('--rvc-url', '-r', default='http://127.0.0.1:5000',
                       help='RVC/Seed-VC server URL (default: http://127.0.0.1:5000)')
    parser.add_argument('--max-concurrent', '-c', type=int, default=3,
                       help='Maximum concurrent processing (default: 3)')
    
    args = parser.parse_args()
    
    # Validate input folder
    if not Path(args.input_folder).exists():
        print(f"❌ Input folder does not exist: {args.input_folder}")
        return
    
    print("🎙️ Audio Translation and Voice Conversion Pipeline")
    print("=" * 55)
    
    # Process files
    async with AudioProcessor(
        input_folder=args.input_folder,
        output_folder=args.output_folder,
        server_url=args.server_url,
        rvc_url=args.rvc_url,
        target_lang=args.target_lang
    ) as processor:
        await processor.process_folder(max_concurrent=args.max_concurrent)

if __name__ == "__main__":
    # Example usage
    if len(os.sys.argv) == 1:
        print("🎙️ Audio Translation and Voice Conversion Pipeline")
        print("=" * 55)
        print("\nUsage:")
        print("  python audio_processor.py input_folder output_folder [options]")
        print("\nExample:")
        print("  python audio_processor.py ./input_audio ./output_audio --target-lang ja")
        print("\nOptions:")
        print("  --target-lang, -t     Target language (default: ja)")
        print("  --server-url, -s      Translation server URL")
        print("  --rvc-url, -r         RVC server URL")
        print("  --max-concurrent, -c  Max concurrent files (default: 3)")
        print("\nSupported audio formats: .wav, .mp3, .m4a, .flac, .ogg, .aac")
    else:
        asyncio.run(main())