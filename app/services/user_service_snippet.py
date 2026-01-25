
    async def upload_avatar(self, user: User, file: UploadFile) -> User:
        """Upload user avatar.

        Args:
            user: User to update.
            file: Uploaded file.

        Returns:
            Updated user.
        """
        # Validate file type
        if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid file type. Only JPEG, PNG and WebP are allowed.",
            )

        # Validate file size
        file.file.seek(0, 2)
        size = file.file.tell()
        await file.seek(0)
        
        if size > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Max size is {settings.MAX_UPLOAD_SIZE_MB}MB.",
            )

        # Create avatar directory
        avatar_dir = Path(settings.UPLOAD_DIR) / "avatars"
        avatar_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename
        ext = file.filename.split(".")[-1] if file.filename else "jpg"
        filename = f"{user.id}.{ext}"
        file_path = avatar_dir / filename

        # Save file
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Update user
        avatar_url = f"/static/uploads/avatars/{filename}"
        user.avatar_url = avatar_url
        user.updated_at = datetime.now(timezone.utc)
        user.updated_by = user.id

        await self.db.commit()
        await self.db.refresh(user)

        logger.info("avatar_uploaded", user_id=str(user.id), filename=filename)

        return user
