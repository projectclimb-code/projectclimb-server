import {
  Body,
  Controller,
  Get,
  Post,
  UploadedFile,
  UseInterceptors,
} from '@nestjs/common';
import { FileInterceptor } from '@nestjs/platform-express';
import { RoutesService } from './routes.service';
import { CreateRouteDto } from 'src/dto/create-route.dto';

@Controller('route')
export class RoutesController {
  constructor(private readonly routesService: RoutesService) {}

  @Post('upload')
  @UseInterceptors(FileInterceptor('file'))
  uploadFile(@UploadedFile() file: CreateRouteDto, @Body() body) {
    this.routesService.create({ ...file, ...body });
  }

  @Get()
  findAll() {
    return this.routesService.findAll();
  }
}
