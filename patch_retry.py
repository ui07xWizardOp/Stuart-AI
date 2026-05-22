import os

filepath = "core/llm_retry_manager.py"
with open(filepath, "rb") as f:
    raw_content = f.read()

# Normalize all line endings (both \r\r\n and \r\n) to \n
content_str = raw_content.decode("utf-8")
clean_content = content_str.replace("\r\r\n", "\n").replace("\r\n", "\n").replace("\r", "\n")

target = """                    # Check if we should retry
                    if attempt >= self.config.max_retries:
                        # Max retries reached
                        self.logger.error(
                            "llm_retry_manager",
                            f"{operation_name} failed after {attempt} attempts",
                            context={
                                "operation_name": operation_name,
                                "attempts": attempt,
                                "final_error": last_error
                            }
                        )
                        
                        # Update statistics
                        self.statistics.update_failure(attempt)
                        
                        span.tags["success"] = False
                        span.tags["attempts"] = attempt
                        
                        return RetryResult(
                            success=False,
                            attempts=attempt,
                            total_delay_seconds=total_delay,
                            error=last_error,
                            retry_history=retry_history
                        )
                    
                    # Calculate delay for next attempt
                    delay = self._calculate_delay(attempt)
                    total_delay += delay
                    
                    # Record retry attempt
                    retry_attempt = RetryAttempt(
                        attempt_number=attempt,
                        timestamp=datetime.utcnow(),
                        delay_seconds=delay,
                        error_message=last_error,
                        validation_errors=validation_errors,
                        prompt_modifications=self._generate_prompt_improvements(validation_errors)
                    )
                    retry_history.append(retry_attempt)"""

replacement = """                    # Calculate delay (0.0 if this is the final attempt)
                    delay = 0.0
                    if attempt < self.config.max_retries:
                        delay = self._calculate_delay(attempt)
                    
                    # Record retry attempt
                    retry_attempt = RetryAttempt(
                        attempt_number=attempt,
                        timestamp=datetime.utcnow(),
                        delay_seconds=delay,
                        error_message=last_error,
                        validation_errors=validation_errors,
                        prompt_modifications=self._generate_prompt_improvements(validation_errors)
                    )
                    retry_history.append(retry_attempt)
                    
                    # Check if we should retry
                    if attempt >= self.config.max_retries:
                        # Max retries reached
                        self.logger.error(
                            "llm_retry_manager",
                            f"{operation_name} failed after {attempt} attempts",
                            context={
                                "operation_name": operation_name,
                                "attempts": attempt,
                                "final_error": last_error
                            }
                        )
                        
                        # Update statistics
                        self.statistics.update_failure(attempt)
                        
                        span.tags["success"] = False
                        span.tags["attempts"] = attempt
                        
                        return RetryResult(
                            success=False,
                            attempts=attempt,
                            total_delay_seconds=total_delay,
                            error=last_error,
                            retry_history=retry_history
                        )
                    
                    # Otherwise update total delay and proceed to wait/retry
                    total_delay += delay"""

if target in clean_content:
    new_content = clean_content.replace(target, replacement)
    # Write as standard LF
    with open(filepath, "w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)
    print("SUCCESS: Normalized line endings and patched core/llm_retry_manager.py successfully.")
else:
    print("ERROR: Target block not found in clean content.")
